import requests
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from urllib.parse import urlparse, parse_qs
import time
from functools import lru_cache
import random

SUMMARY_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
QA_API_URL = "https://api-inference.huggingface.co/models/deepset/roberta-base-squad2"
summary_headers = {"Authorization": "Bearer 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"}
qa_headers = {"Authorization": "Bearer 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"}

# Cache for storing transcripts
@lru_cache(maxsize=100)
def cached_get_transcript(video_id):
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    try:
        transcript = transcript_list.find_manually_created_transcript(['en'])
    except:
        try:
            transcript = transcript_list.find_generated_transcript(['en'])
        except:
            # Try to find any English transcript
            for transcript in transcript_list:
                if transcript.language_code.startswith('en'):
                    return transcript.fetch()
            # If no English transcript found, try the first available transcript
            return transcript_list[0].fetch()
    return transcript.fetch()

def query(api_url, headers, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                st.error(f"API request failed after {max_retries} attempts: {str(e)}")
                return None
            time.sleep(2 ** attempt)  # Exponential backoff
    return None

def chunk_text(text, max_length=512):
    words = text.split()
    for i in range(0, len(words), max_length):
        yield ' '.join(words[i:i + max_length])

def generate_summary(text):
    try:
        summaries = []
        total_chunks = len(list(chunk_text(text)))
        progress_bar = st.progress(0)
        progress_text = st.empty()
        start_time = time.time()

        for i, chunk in enumerate(chunk_text(text)):
            chunk_length = len(chunk.split())
            min_len, max_len = (1, 60) if chunk_length <= 150 else (70, 130) if chunk_length <= 300 else (130, 280)

            output = query(SUMMARY_API_URL, summary_headers, {
                "inputs": chunk,
                "parameters": {"min_length": min_len, "max_length": max_len}
            })
            
            if output:
                summaries.append(output[0]['summary_text'])
                progress_bar.progress((i + 1) / total_chunks)
                progress_text.text(f"Progress: {int((i + 1) / total_chunks * 100)}%")
            else:
                st.error("Failed to generate summary for a chunk")
                return None, None

        progress_bar.empty()
        progress_text.empty()
        elapsed_time = time.time() - start_time
        return ' '.join(summaries), elapsed_time
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")
        return None, None

def extract_video_id(url):
    try:
        parsed_url = urlparse(url)
        if parsed_url.hostname == 'youtu.be':
            return parsed_url.path[1:]
        if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed_url.path == '/watch':
                return parse_qs(parsed_url.query)['v'][0]
            elif parsed_url.path[:7] == '/embed/':
                return parsed_url.path.split('/')[2]
            elif parsed_url.path[:3] == '/v/':
                return parsed_url.path.split('/')[2]
        return None
    except Exception:
        return None

def get_transcript(url):
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return "Error: Could not extract video ID from URL", None

        # Add random delay between 1-3 seconds
        time.sleep(random.uniform(1, 3))
        
        try:
            # Try to get from cache first
            transcript_data = cached_get_transcript(video_id)
            
            # Format the transcript
            formatter = TextFormatter()
            formatted_transcript = formatter.format_transcript(transcript_data)
            
            return formatted_transcript, video_id

        except Exception as e:
            # If there's an error with the primary method, try the basic approach
            try:
                time.sleep(2)  # Wait before retry
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                return " ".join(entry['text'] for entry in transcript_data), video_id
            except Exception as inner_e:
                return f"Error: Could not retrieve transcript. {str(inner_e)}", None

    except Exception as e:
        return f"Error: {str(e)}", None

# Initialize session state for caching
if 'transcript_cache' not in st.session_state:
    st.session_state.transcript_cache = {}

# Streamlit Interface
st.markdown(
    """
    <h1 style="background: -webkit-linear-gradient(#a0eaff, #85d1e5); 
               -webkit-background-clip: text; 
               color: transparent;
               text-align: center;
               padding: 20px;">
        TubeIntel: Summarize Video and Ask Questions
    </h1>
    """,
    unsafe_allow_html=True
)

# Add cache control to sidebar
with st.sidebar:
    st.header("Cache Control")
    if st.button("Clear Cache"):
        cached_get_transcript.cache_clear()
        st.session_state.transcript_cache = {}
        st.success("Cache cleared!")

video_url = st.text_input("YouTube Video URL")
choice = st.radio("Choose an action:", ('Generate Summary', 'Ask Questions'))

if video_url:
    # Show loading spinner while fetching transcript
    with st.spinner("Fetching video transcript..."):
        transcript, video_id = get_transcript(video_url)
    
    if video_id:
        if choice == 'Generate Summary':
            st.write("Generating summary...")
            summary_result = generate_summary(transcript)
            
            if summary_result:
                summary, elapsed_time = summary_result
                st.success("Summary generated successfully!")
                st.subheader("Summary")
                st.text_area("Video Summary", value=summary, height=300, max_chars=5000)
                st.write(f"Time taken to generate summary: {elapsed_time:.2f} seconds")
                st.download_button("Download Summary", data=summary, file_name=f"summary_{video_id}.txt", mime="text/plain")

        elif choice == 'Ask Questions':
            st.subheader("Ask Questions About the Video")
            question = st.text_input("Enter your question:")

            if st.button("Get Answer"):
                if question:
                    with st.spinner("Finding answer..."):
                        output = query(QA_API_URL, qa_headers, {
                            "inputs": {"question": question, "context": transcript}
                        })
                    
                    if output:
                        answer = output.get("answer", "No answer found.")
                        confidence = output.get("score", 0) * 100

                        confidence_color = "green" if confidence > 70 else "yellow" if confidence >= 50 else "red"
                        st.write(f"Answer: {answer}")
                        st.markdown(
                            f"<span style='color:{confidence_color}; font-weight:bold;'>Confidence: {confidence:.2f}%</span>",
                            unsafe_allow_html=True
                        )
                else:
                    st.write("Please enter a question.")
    else:
        st.error(transcript)
else:
    st.write("Please enter a valid YouTube URL.")

# Footer
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <p style='color: #666;'>Made with ❤️ by TubeIntel</p>
</div>
""", unsafe_allow_html=True)
