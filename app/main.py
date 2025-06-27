from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime, timedelta
import uuid
from pydantic import BaseModel
from typing import Optional, Literal, List, Tuple
import shutil
from pathlib import Path

from .generators.story import generate_story
from .generators.educational import generate_educational_content
from .generators.image import generate_images
from .generators.audio import generate_voice_over, generate_background_music, generate_dialogue, generate_music, generate_audiobook
from .generators.video import create_video_async
from .generators.podcast import (
    generate_podcast_from_custom_text,
    generate_podcast_from_topic,
    generate_free_podcast,
    generate_dialogue_content
)
from .generators.article import generate_article
from .generators.social import generate_tweet_thread
from .generators.book import generate_book_chapter
import json # For saving tweet_thread output
from .config import OUTPUT_DIR
from app.api import games

# Define request models
class DialogueEntry(BaseModel):
    speaker: int  # 1 or 2
    text: str

class PodcastGenerationOptions(BaseModel):
    podcast_type: Literal["custom_text", "topic_based", "free_generation", "dialogue"]
    custom_text: Optional[str] = None
    topic: Optional[str] = None
    dialogues: Optional[List[DialogueEntry]] = None
    voice1: Optional[str] = "rachel"  # Default female voice
    voice2: Optional[str] = "josh"    # Default male voice
    num_exchanges: Optional[int] = Query(default=6, ge=2, le=20)  # Number of dialogue exchanges to generate

class ArticleOptions(BaseModel):
    custom_instructions: Optional[str] = None
    # placeholder for future article-specific options like section_titles, target_audience

class TweetOptions(BaseModel):
    num_tweets: int = Query(default=3, ge=1, le=10) # Default to 3 tweets, min 1, max 10
    call_to_action: Optional[str] = None
    # placeholder for future tweet-specific options like tone (e.g. "professional", "witty")

class BookChapterOptions(BaseModel):
    plot_summary: Optional[str] = None
    chapter_topic: Optional[str] = None # More specific topic for the chapter
    previous_chapter_summary: Optional[str] = None
    characters: Optional[List[str]] = None
    genre: Optional[str] = None
    # placeholder for future book-specific options

class ContentRequest(BaseModel):
    content_type: Literal["story", "educational", "podcast", "article", "tweet_thread", "book_chapter", "music", "audiobook"]
    topic: Optional[str] = None  # character_description for stories, topic for educational content, primary subject for text types

    # New fields for music and audiobook
    music_prompt: Optional[str] = None
    audiobook_text: Optional[str] = None

    # Video/Educational specific (could be refactored further if more types emerge)
    video_prompt: Optional[str] = None
    educational_style: Optional[Literal["lecture", "tutorial", "explainer"]] = None
    difficulty_level: Optional[Literal["beginner", "intermediate", "advanced"]] = None

    # Podcast specific
    podcast_options: Optional[PodcastGenerationOptions] = None
    voice_name: Optional[str] = None  # Name of the ElevenLabs voice to use

    # New text-specific options
    article_options: Optional[ArticleOptions] = None
    tweet_options: Optional[TweetOptions] = None
    book_chapter_options: Optional[BookChapterOptions] = None

    # Common text generation parameters
    desired_length_words: Optional[int] = Query(default=0, ge=0) # 0 might mean model default or not applicable
    style_tone: Optional[str] = None  # e.g., "formal", "casual", "technical", "humorous"


# Add new models
class VideoInfo(BaseModel):
    job_id: str
    content_type: str
    created_at: str
    video_url: str
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None

app = FastAPI(
    title="Content Maker API",
    description="API for generating AI-powered stories and educational videos with images, voice-overs, and background music",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active jobs
active_jobs = {}

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create necessary directories
os.makedirs("static/videos", exist_ok=True)
os.makedirs("static/thumbnails", exist_ok=True)
os.makedirs("static/audios", exist_ok=True)

app.include_router(games.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Content Maker API"}

@app.post("/generate")
async def generate_content_endpoint(request: ContentRequest, background_tasks: BackgroundTasks):
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Create a unique output directory for this job
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)
    
    # Store job information
    active_jobs[job_id] = {
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "output_dir": output_dir,
        "content_type": request.content_type,
        "video_prompt": request.video_prompt
    }
    
    # Start the generation process in the background
    background_tasks.add_task(
        process_content_generation,
        job_id,
        request,
        output_dir
    )
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"{request.content_type.capitalize()} generation started"
    }

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return active_jobs[job_id]

@app.get("/download/{job_id}")
async def download_content(job_id: str):
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_info = active_jobs[job_id]
    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Content generation not completed")

    output_filename = job_info.get("output_filename")
    media_type = job_info.get("media_type")
    content_type = job_info["content_type"] # Original content type for filename construction

    if not output_filename or not media_type:
        # Fallback for older jobs or if these keys weren't stored (should not happen for new jobs)
        if content_type == "podcast":
            output_filename = "podcast_audio.mp3"
            media_type = "audio/mpeg"
        elif content_type in ["story", "educational"]:
            output_filename = "content_video.mp4"
            media_type = "video/mp4"
        else:
            raise HTTPException(status_code=500, detail="Job output information is incomplete.")

    file_path = os.path.join(job_info["output_dir"], output_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"{output_filename} not found in job output.")

    # Construct a user-friendly download filename
    base_filename, file_ext = os.path.splitext(output_filename)
    if not file_ext: # for cases where output_filename might not have an extension (e.g. from older setup)
        if media_type == "application/json": file_ext = ".json"
        elif media_type == "text/plain": file_ext = ".txt"
        elif media_type == "audio/mpeg": file_ext = ".mp3"
        elif media_type == "video/mp4": file_ext = ".mp4"
        else: file_ext = "" # Default if unknown

    download_filename = f"{content_type}_{job_id}{file_ext}"

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=download_filename
    )

@app.get("/videos", response_model=List[VideoInfo])
async def list_videos(
    content_type: Optional[str] = None,
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(10, ge=1, le=100)
):
    """List available videos with optional filtering."""
    videos = []
    cutoff_date = datetime.now() - timedelta(days=days)
    
    for job_id, job_info in active_jobs.items():
        if job_info["status"] != "completed":
            continue
            
        if content_type and job_info["content_type"] != content_type:
            continue
            
        created_at = datetime.fromisoformat(job_info["created_at"])
        if created_at < cutoff_date:
            continue
            
        video_path = os.path.join(job_info["output_dir"], "content_video.mp4")
        if not os.path.exists(video_path):
            continue
            
        # Create public URL for the video
        public_path = f"static/videos/{job_id}.mp4"
        if not os.path.exists(public_path):
            shutil.copy2(video_path, public_path)
            
        videos.append(VideoInfo(
            job_id=job_id,
            content_type=job_info["content_type"],
            created_at=job_info["created_at"],
            video_url=f"/static/videos/{job_id}.mp4"
        ))
    
    return sorted(videos, key=lambda x: x.created_at, reverse=True)[:limit]

@app.get("/video/{job_id}/stream")
async def stream_video(job_id: str):
    """Stream video content."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Video not found")
    
    job_info = active_jobs[job_id]
    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video generation not completed")
    
    video_path = os.path.join(job_info["output_dir"], "content_video.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return StreamingResponse(
        open(video_path, "rb"),
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'attachment; filename="{job_info["content_type"]}_{job_id}.mp4"'
        }
    )

@app.get("/video/{job_id}/embed")
async def get_video_embed(job_id: str):
    """Get HTML embed code for the video."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Video not found")
    
    job_info = active_jobs[job_id]
    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video generation not completed")
    
    video_url = f"/static/videos/{job_id}.mp4"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{job_info['content_type'].capitalize()} Video</title>
        <style>
            body {{ margin: 0; padding: 20px; background: #f0f0f0; }}
            .video-container {{ max-width: 800px; margin: 0 auto; }}
            video {{ width: 100%; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <div class="video-container">
            <video controls>
                <source src="{video_url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

@app.get("/video/{job_id}/info")
async def get_video_info(job_id: str):
    """Get detailed information about a video."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Video not found")
    
    job_info = active_jobs[job_id]
    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video generation not completed")
    
    video_path = os.path.join(job_info["output_dir"], "content_video.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Get video file size
    file_size = os.path.getsize(video_path)
    
    return {
        "job_id": job_id,
        "content_type": job_info["content_type"],
        "created_at": job_info["created_at"],
        "completed_at": job_info["completed_at"],
        "file_size": file_size,
        "download_url": f"/download/{job_id}",
        "stream_url": f"/video/{job_id}/stream",
        "embed_url": f"/video/{job_id}/embed",
        "static_url": f"/static/videos/{job_id}.mp4"
    }

async def process_content_generation(job_id: str, request: ContentRequest, output_dir: str):
    try:
        output_filename = None
        media_type = None
        text_content_only = False # Flag to skip media generation for text-only types

        if request.content_type == "story" or request.content_type == "educational":
            if request.content_type == "story":
                content = await generate_story(request.topic)
            else: # educational
                content = await generate_educational_content(
                    request.topic,
                    request.educational_style,
                    request.difficulty_level
                )
            output_filename = "content.txt"
            media_type = "text/plain" # For the script itself
            with open(os.path.join(output_dir, output_filename), 'w') as f:
                f.write(content)

            # These types will proceed to media generation

        elif request.content_type == "podcast":
            text_content_only = True # Podcast audio is handled, but no video/images unless specified
            if not request.podcast_options:
                raise ValueError("Podcast options not provided for podcast content type.")

            if request.podcast_options.podcast_type == "dialogue":
                # Generate dialogue content if not provided
                if not request.podcast_options.dialogues:
                    if not request.topic:
                        raise HTTPException(status_code=400, detail="Topic is required for automatic dialogue generation")
                    
                    # Generate dialogue content
                    dialogue_list = await generate_dialogue_content(
                        topic=request.topic,
                        num_exchanges=request.podcast_options.num_exchanges
                    )
                else:
                    # Use provided dialogues
                    dialogue_list = [(d.speaker, d.text) for d in request.podcast_options.dialogues]
                
                # Generate dialogue audio
                output_filename = "podcast_audio.mp3"
                output_path = os.path.join(output_dir, output_filename)
                await generate_dialogue(
                    dialogues=dialogue_list,
                    output_path=output_path,
                    voice1=request.podcast_options.voice1,
                    voice2=request.podcast_options.voice2
                )
                
                # Update job info
                active_jobs[job_id].update({
                    "status": "completed",
                    "output_filename": output_filename,
                    "media_type": "audio/mpeg"
                })
            else:
                # Handle other podcast types as before
                if request.podcast_options.podcast_type == "custom_text":
                    text = request.podcast_options.custom_text
                elif request.podcast_options.podcast_type == "topic_based":
                    text = await generate_podcast_from_topic(request.topic)
                else:  # free_generation
                    text = await generate_free_podcast()
                
                # Generate voice over
                output_filename = "podcast_audio.mp3"
                output_path = os.path.join(output_dir, output_filename)
                await generate_voice_over(
                    text=text,
                    output_path=output_path,
                    voice_name=request.voice_name
                )
                
                # Update job info
                active_jobs[job_id].update({
                    "status": "completed",
                    "output_filename": output_filename,
                    "media_type": "audio/mpeg"
                })

        elif request.content_type == "music":
            if not request.music_prompt:
                raise HTTPException(status_code=400, detail="Music prompt is required for music generation.")
            
            output_filename = "music.mp3"
            output_path = os.path.join(output_dir, output_filename)
            await generate_music(request.music_prompt, output_path)
            
            active_jobs[job_id].update({
                "status": "completed",
                "output_filename": output_filename,
                "media_type": "audio/mpeg"
            })
            text_content_only = True # No video/images for music

        elif request.content_type == "audiobook":
            if not request.audiobook_text:
                raise HTTPException(status_code=400, detail="Audiobook text is required for audiobook generation.")
            
            output_filename = "audiobook.mp3"
            output_path = os.path.join(output_dir, output_filename)
            await generate_audiobook(request.audiobook_text, output_path, request.voice_name)
            
            active_jobs[job_id].update({
                "status": "completed",
                "output_filename": output_filename,
                "media_type": "audio/mpeg"
            })
            text_content_only = True # No video/images for audiobook

        elif request.content_type == "article":
            text_content_only = True
            if not request.article_options:
                # Providing default empty options if None, or raise error if it must be provided
                request.article_options = ArticleOptions() # Or raise ValueError

            generated_text = await generate_article(
                topic=request.topic,
                desired_length_words=request.desired_length_words or 0,
                style_tone=request.style_tone,
                custom_instructions=request.article_options.custom_instructions
            )
            if generated_text.startswith("Error:"):
                raise ValueError(f"Article generation failed: {generated_text}")

            output_filename = "article.txt"
            media_type = "text/plain"
            with open(os.path.join(output_dir, output_filename), 'w') as f:
                f.write(generated_text)
            active_jobs[job_id]["output_filename"] = output_filename
            active_jobs[job_id]["media_type"] = media_type

        elif request.content_type == "tweet_thread":
            text_content_only = True
            if not request.tweet_options:
                request.tweet_options = TweetOptions() # Or raise ValueError

            tweet_list = await generate_tweet_thread(
                topic=request.topic,
                num_tweets=request.tweet_options.num_tweets,
                style_tone=request.style_tone,
                call_to_action=request.tweet_options.call_to_action,
                custom_instructions=None # Assuming not yet added to TweetOptions in this example
            )
            if isinstance(tweet_list, list) and tweet_list and tweet_list[0].startswith("Error:"):
                 raise ValueError(f"Tweet thread generation failed: {tweet_list[0]}")

            output_filename = "tweet_thread.json"
            media_type = "application/json"
            with open(os.path.join(output_dir, output_filename), 'w') as f:
                json.dump(tweet_list, f, indent=2)
            active_jobs[job_id]["output_filename"] = output_filename
            active_jobs[job_id]["media_type"] = media_type

        elif request.content_type == "book_chapter":
            text_content_only = True
            if not request.book_chapter_options:
                request.book_chapter_options = BookChapterOptions() # Or raise ValueError

            generated_text = await generate_book_chapter(
                plot_summary=request.book_chapter_options.plot_summary,
                chapter_topic=request.book_chapter_options.chapter_topic or request.topic,
                previous_chapter_summary=request.book_chapter_options.previous_chapter_summary,
                characters=request.book_chapter_options.characters,
                genre=request.book_chapter_options.genre,
                style_tone=request.style_tone,
                desired_length_words=request.desired_length_words or 0,
                custom_instructions=None # Assuming not yet added to BookChapterOptions
            )
            if generated_text.startswith("Error:"):
                raise ValueError(f"Book chapter generation failed: {generated_text}")

            output_filename = "book_chapter.txt"
            media_type = "text/plain"
            with open(os.path.join(output_dir, output_filename), 'w') as f:
                f.write(generated_text)
            active_jobs[job_id]["output_filename"] = output_filename
            active_jobs[job_id]["media_type"] = media_type

        else:
            raise ValueError(f"Unsupported content type: {request.content_type}")

        # --- Media Generation (only for specific types) ---
        if not text_content_only and (request.content_type == "story" or request.content_type == "educational"):
            # This block is for story and educational which produce video
            # Content was already fetched and saved as content.txt for these types
            script_content_path = os.path.join(output_dir, "content.txt")
            with open(script_content_path, 'r') as f:
                content_for_media = f.read()

            image_paths = await generate_images(
                content_for_media,
                request.topic,
                output_dir,
                content_type=request.content_type
            )

            voice_over_path = os.path.join(output_dir, "voice_over.mp3")
            await generate_voice_over(content_for_media, voice_over_path)

            background_music_path = os.path.join(output_dir, "background_music.wav")
            await generate_background_music(60, background_music_path)

            video_path = os.path.join(output_dir, "content_video.mp4") # Main output for these types
            await create_video_async(
                image_paths,
                voice_over_path,
                background_music_path,
                video_path,
                video_prompt=request.video_prompt,
                content_type=request.content_type
            )
            active_jobs[job_id]["output_filename"] = "content_video.mp4" # For download
            active_jobs[job_id]["media_type"] = "video/mp4" # For download

        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)
        active_jobs[job_id]["failed_at"] = datetime.now().isoformat()

@app.get("/podcast/{job_id}/info")
async def get_podcast_info(job_id: str):
    """Get detailed information about a podcast job."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_info = active_jobs[job_id]
    if job_info["content_type"] != "podcast":
        raise HTTPException(status_code=400, detail="Job is not a podcast type.")

    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Podcast generation not completed.")

    return {
        "job_id": job_id,
        "content_type": job_info["content_type"],
        "created_at": job_info["created_at"],
        "completed_at": job_info["completed_at"],
        "audio_url": job_info.get("audio_url"),
        "download_url": f"/download/{job_id}",
        # "script_url": f"/download/{job_id}?type=script" # Example for future script download
    }