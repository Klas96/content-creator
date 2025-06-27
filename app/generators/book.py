from typing import Optional, List, Dict, Any
from app.llm_clients import generate_text_completion
from app.config import TEST_MODE
from app.utils import load_prompt
import json
import subprocess
import os

async def generate_book_chapter(
    plot_summary: Optional[str] = None,
    chapter_topic: Optional[str] = None,
    previous_chapter_summary: Optional[str] = None,
    characters: Optional[List[str]] = None,
    genre: Optional[str] = None,
    style_tone: Optional[str] = None, # Added from ContentRequest common params
    desired_length_words: int = 0, # Added from ContentRequest common params
    custom_instructions: Optional[str] = None # Added for consistency
) -> str:
    """
    Generates a book chapter using the configured LLM.
    This is a basic version and can be significantly enhanced.
    """
    if TEST_MODE:
        return (f"Test Mode: Book chapter. Genre: {genre}, Style: {style_tone}.\n"
                f"Chapter Topic: {chapter_topic}\nPlot Summary: {plot_summary}\n"
                f"Characters: {', '.join(characters) if characters else 'N/A'}\n"
                f"Previous Chapter Summary: {previous_chapter_summary}\n"
                f"Desired Length: {desired_length_words} words.\n"
                f"Custom Instructions: {custom_instructions}")

    # Construct optional sections
    characters_section_str = ""
    if characters:
        characters_section_str = f"Key characters in this chapter might include: {', '.join(characters)}."

    plot_summary_section_str = ""
    if plot_summary:
        plot_summary_section_str = f"Overall plot summary of the book: {plot_summary}"

    previous_chapter_summary_section_str = ""
    if previous_chapter_summary:
        previous_chapter_summary_section_str = (
            f"Summary of the previous chapter: {previous_chapter_summary}\n"
            "Ensure this new chapter follows logically from the previous one."
        )

    custom_instructions_section_str = ""
    if custom_instructions:
        custom_instructions_section_str = f"Follow these additional instructions: {custom_instructions}"

    prompt = load_prompt(
        "book_chapter_generator_prompt.txt",
        genre=genre if genre else "not specified",
        style_tone=style_tone if style_tone else "neutral",
        characters_section=characters_section_str,
        plot_summary_section=plot_summary_section_str,
        previous_chapter_summary_section=previous_chapter_summary_section_str,
        chapter_topic=chapter_topic if chapter_topic else "not specified", # Or let template handle it
        desired_length_words=str(desired_length_words) if desired_length_words > 0 else "not specified",
        custom_instructions_section=custom_instructions_section_str
    )

    if prompt.startswith("Error:"): # Check for errors from load_prompt
        return prompt # Propagate error

    calculated_max_tokens = 0
    if desired_length_words > 0:
        calculated_max_tokens = int(desired_length_words * 1.6) # Slightly higher factor for prose
    else:
        # Default for a chapter can be quite large, e.g., 3000-4000 words.
        # Anthropic's Claude-2 has a 100k token context window, but max_tokens_to_sample is often less for one-off completion.
        # Let's set a large default, but be mindful of LLM limits for single call.
        calculated_max_tokens = 3000 # Default tokens, might be ~2000 words. Can be increased.

    chapter_text = await generate_text_completion(
        prompt=prompt,
        temperature=0.75, # Slightly higher temp for more creative writing
        max_tokens=calculated_max_tokens
    )

    if chapter_text.startswith("Error:"): # Propagate errors
        return f"Error generating book chapter: {chapter_text}" # Or handle more gracefully

    return chapter_text

async def generate_book_outline(
    book_topic: str,
    genre: Optional[str] = None,
    num_chapters: int = 10,
    style_tone: Optional[str] = None,
    custom_instructions: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a book outline including plot summary, character descriptions,
    and chapter-by-chapter summaries.
    """
    if TEST_MODE:
        return {
            "plot_summary": f"Test Mode: Plot summary for a {genre} book about {book_topic}.",
            "characters": ["Test Character 1", "Test Character 2"],
            "chapters": [
                {"title": f"Chapter 1: Introduction to {book_topic}", "summary": "Summary of chapter 1."},
                {"title": f"Chapter 2: Developing {book_topic}", "summary": "Summary of chapter 2."
            ]
        }

    prompt = load_prompt(
        "book_outline_generator_prompt.txt",
        book_topic=book_topic,
        genre=genre if genre else "not specified",
        num_chapters=str(num_chapters),
        style_tone=style_tone if style_tone else "neutral",
        custom_instructions=custom_instructions if custom_instructions else ""
    )

    if prompt.startswith("Error:"):
        return {"error": prompt}

    # Max tokens for outline generation should be sufficient for a structured JSON output
    # A chapter summary might be 50-100 words, so 10 chapters * 100 words * 1.6 tokens/word = 1600 tokens
    # Plus plot and characters, let's aim for 2000-3000 tokens.
    outline_text = await generate_text_completion(
        prompt=prompt,
        temperature=0.7,
        max_tokens=3000
    )

    if outline_text.startswith("Error:"):
        return {"error": f"Error generating book outline: {outline_text}"}

    try:
        # Assuming the LLM is instructed to output JSON
        outline = json.loads(outline_text)
        return outline
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from outline generation: {e}")
        print(f"LLM Output: {outline_text}")
        return {"error": "Failed to parse book outline from LLM response. Invalid JSON format."}

async def generate_book(
    book_topic: str,
    genre: Optional[str] = None,
    num_chapters: int = 10,
    style_tone: Optional[str] = None,
    custom_instructions: Optional[str] = None,
    desired_chapter_length_words: int = 0
) -> Dict[str, Any]:
    """
    Generates a complete book by first creating an outline and then
    generating each chapter.
    """
    if TEST_MODE:
        print(f"Test Mode: Generating book for topic: {book_topic}")
        outline = await generate_book_outline(book_topic, genre, num_chapters, style_tone, custom_instructions)
        if "error" in outline:
            return outline
        
        book_content = []
        for i, chapter_info in enumerate(outline.get("chapters", [])):
            chapter_text = await generate_book_chapter(
                plot_summary=outline.get("plot_summary"),
                chapter_topic=chapter_info.get("summary"),
                previous_chapter_summary=f"Summary of previous chapter {i} (mock)",
                characters=outline.get("characters"),
                genre=genre,
                style_tone=style_tone,
                desired_length_words=desired_chapter_length_words,
                custom_instructions=custom_instructions
            )
            book_content.append(f"## {chapter_info.get('title', f'Chapter {i+1}')}\n\n{chapter_text}\n\n")
        
        return {
            "title": f"Test Book: {book_topic}",
            "plot_summary": outline.get("plot_summary"),
            "characters": outline.get("characters"),
            "chapters": outline.get("chapters"),
            "full_book_content": "".join(book_content)
        }

    print(f"Generating outline for book: {book_topic} ({num_chapters} chapters)")
    outline = await generate_book_outline(book_topic, genre, num_chapters, style_tone, custom_instructions)

    if "error" in outline:
        return outline

    full_book_content = []
    previous_chapter_summary = None

    for i, chapter_info in enumerate(outline.get("chapters", [])):
        print(f"Generating chapter {i+1}: {chapter_info.get('title', 'Untitled Chapter')}")
        chapter_text = await generate_book_chapter(
            plot_summary=outline.get("plot_summary"),
            chapter_topic=chapter_info.get("summary"), # Use chapter summary as topic
            previous_chapter_summary=previous_chapter_summary,
            characters=outline.get("characters"),
            genre=genre,
            style_tone=style_tone,
            desired_length_words=desired_chapter_length_words,
            custom_instructions=custom_instructions
        )

        if chapter_text.startswith("Error:"):
            return {"error": f"Failed to generate chapter {i+1}: {chapter_text}"}
        
        full_book_content.append(f"## {chapter_info.get('title', f'Chapter {i+1}')}\n\n{chapter_text}\n\n")
        previous_chapter_summary = chapter_info.get("summary") # Update for next chapter

    book_data = {
        "title": outline.get("title", f"Book: {book_topic}"),
        "plot_summary": outline.get("plot_summary"),
        "characters": outline.get("characters"),
        "chapters": outline.get("chapters"),
        "full_book_content": "".join(full_book_content)
    }
    return book_data

async def generate_book_pdf(book_title: str, book_content: str, output_dir: str) -> str:
    """
    Generates a PDF file from book content using LaTeX.
    """
    if TEST_MODE:
        pdf_path = os.path.join(output_dir, "book.pdf")
        with open(pdf_path, "w") as f:
            f.write(f"Mock PDF content for: {book_title}\n{book_content[:100]}...")
        print(f"Test mode: Generated mock PDF at {pdf_path}")
        return pdf_path

    template_path = "templates/book_template.tex"
    output_tex_path = os.path.join(output_dir, "book.tex")
    output_pdf_path = os.path.join(output_dir, "book.pdf")

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            latex_template = f.read()

        # Escape LaTeX special characters in content
        # This is a basic escaping, more robust solution might be needed for complex text
        latex_content = book_content.replace("&", "\\&")\
                                    .replace("%", "\\%")\
                                    .replace("$", "\\$")\
                                    .replace("#", "\\#")\
                                    .replace("_", "\\_")\
                                    .replace("{", "\\{")\
                                    .replace("}", "\\}")\
                                    .replace("~", "\\textasciitilde{}")\
                                    .replace("^", "\\textasciicircum{}")\
                                    .replace("\\", "\\textbackslash{}")\
                                    .replace("<", "\\textless{}")\
                                    .replace(">", "\\textgreater{}")

        # Replace chapter titles with LaTeX sections
        # Assuming chapters are marked with "## Chapter Title"
        latex_content = latex_content.replace("## ", "\\chapter*{")
        latex_content = latex_content.replace("\n\n", "}\\n\\n") # Close chapter title

        final_latex = latex_template.replace("<<BOOK_TITLE>>", book_title)\
                                    .replace("<<BOOK_CONTENT>>", latex_content)

        with open(output_tex_path, "w", encoding="utf-8") as f:
            f.write(final_latex)

        # Compile LaTeX to PDF
        # Run pdflatex twice for table of contents and references to be correct
        print(f"Compiling LaTeX file: {output_tex_path}")
        process1 = await asyncio.create_subprocess_exec(
            "pdflatex", "-output-directory", output_dir, output_tex_path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout1, stderr1 = await process1.communicate()
        print(f"pdflatex stdout (1st pass):\n{stdout1.decode()}")
        if stderr1:
            print(f"pdflatex stderr (1st pass):\n{stderr1.decode()}")

        process2 = await asyncio.create_subprocess_exec(
            "pdflatex", "-output-directory", output_dir, output_tex_path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout2, stderr2 = await process2.communicate()
        print(f"pdflatex stdout (2nd pass):\n{stdout2.decode()}")
        if stderr2:
            print(f"pdflatex stderr (2nd pass):\n{stderr2.decode()}")

        if not os.path.exists(output_pdf_path):
            raise Exception(f"PDF file not created. pdflatex output: {stdout2.decode()} {stderr2.decode()}")

        print(f"PDF generated successfully at: {output_pdf_path}")
        return output_pdf_path

    except FileNotFoundError:
        raise Exception("pdflatex command not found. Please ensure LaTeX is installed and in your PATH.")
    except Exception as e:
        raise Exception(f"Error generating PDF: {e}")
    finally:
        # Clean up auxiliary files
        for ext in [".aux", ".log", ".out", ".toc", ".lof", ".lot", ".bbl", ".blg", ".fls", ".fdb_latexmk"]:
            if os.path.exists(output_tex_path.replace(".tex", ext)):
                os.remove(output_tex_path.replace(".tex", ext))

# Example usage (for testing purposes)
# if __name__ == "__main__":
#     import asyncio
#     async def test_book_generation():
#         # Test outline generation
#         # outline = await generate_book_outline(
#         #     book_topic="A detective solving a mystery in a futuristic city",
#         #     genre="cyberpunk mystery",
#         #     num_chapters=3
#         # )
#         # print("\n--- Generated Outline ---")
#         # print(json.dumps(outline, indent=2))

#         # Test full book generation
#         book = await generate_book(
#             book_topic="The last dragon's journey",
#             genre="fantasy",
#             num_chapters=2,
#             style_tone="epic and melancholic",
#             desired_chapter_length_words=500
#         )
#         print("\n--- Generated Book ---")
#         if "error" in book:
#             print(book["error"])
#         else:
#             print(book["full_book_content"])

#     asyncio.run(test_book_generation())
