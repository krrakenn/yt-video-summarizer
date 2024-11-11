# app.py
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import streamlit as st
import os

# Function to extract video ID
def extract_video_id(url):
    parsed_url = urlparse(url)
    if parsed_url.query:
        query_params = parse_qs(parsed_url.query)
        if 'v' in query_params:
            return query_params['v'][0]
    path = parsed_url.path.split('/')
    if len(path) > 1:
        return path[-1]
    return None

# Function to get transcript
def get_transcript(url):
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return "Error: Could not extract video ID from URL", None
        # Get list of available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try transcripts in priority order
        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            transcript = transcript_list.find_generated_transcript(['en'])
        # Get the actual transcript
        transcript_data = transcript.fetch()
        # Combine all text entries
        full_transcript = " ".join([entry['text'] for entry in transcript_data])
        return full_transcript, video_id
    except Exception as e:
        return f"Error: {str(e)}", None

# Streamlit interface
st.title("YouTube Transcript Extractor and Saver")
st.write("Enter a YouTube link to extract the transcript.")

# Input for YouTube link
video_url = st.text_input("YouTube Video URL")

if st.button("Extract Transcript"):
    if not video_url:
        st.write("Please enter a valid YouTube URL.")
    else:
        with st.spinner("Extracting transcript..."):
            transcript, video_id = get_transcript(video_url)
        if video_id:
            # Save transcript locally
            if not os.path.exists('transcripts'):
                os.makedirs('transcripts')
            filename = f"transcripts/transcript_{video_id}.txt"
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(transcript)
            st.success(f"Transcript saved to: {filename}")
        st.subheader("Transcript")
        st.write(transcript)
