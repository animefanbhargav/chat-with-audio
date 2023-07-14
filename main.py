
import logging

import os

import streamlit as st
from audio_recorder_streamlit import audio_recorder

from speech_tools.transcriber import Transcriber
from query_handler.huggingface_query_handler import LLMQueryHandler


from utils.constants import Language, FileType


logging.basicConfig(
    filename='debug.log',
    filemode="w",
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

st.title('Audio Q&A')


# Initialize api key
if 'api_key' not in st.session_state:
    st.session_state.api_key = None

# Select Free or Paid mode
if not st.session_state.api_key:
    api_key_container = st.container()
    st.session_state.api_key = None
    with api_key_container.container():
        st.write('You have the flexibility to choose between two options:')
        options = ["**Paid Version:** Includes Whisper for transcription and gpt-3.5-turbo for Q&A. Reliable, high-quality results.",
                   "**Free Version:** Powered by Falcon-7b and GoogleSpeechRecognition API (free version). Although slower and less predictable, it offers a cost-effective \
                    opportunity to explore audio processing capabilities. Experiment and evaluate its suitability for your needs."]
        for opt in options:
            st.markdown('- '+opt)
        api_key_options = ["Enter Api Key", "Free"]
        option = st.radio(
            label='Select an Option',
            options=api_key_options,
            key='api_key_radio',
            horizontal=True
        )
        if option == api_key_options[0]:
            if api_key := st.text_input("OpenAI API Key", type='password', placeholder="Enter OpenAI API Key"):
                st.session_state.api_key = api_key
                os.environ["OPENAI_API_KEY"] = api_key

        else:
            st.session_state.api_key = 'free'


@st.cache_resource(show_spinner="Loading embeddings..May take several minutes...")
def query_handler_object():
    return LLMQueryHandler()


@st.cache_resource(show_spinner=False)
def transcriber_object():
    return Transcriber()


@st.cache_resource(show_spinner=False, hash_funcs={list: lambda x: ''.join([str(y.page_content) for y in x])})
def load_text(docs):
    st.session_state.messages = []
    if len(docs) == 0:
        raise ValueError("Transcribed Text is Empty")
    query_handler.load_text(docs)


if st.session_state.api_key == 'free':
    query_handler = query_handler_object()


# streamlit framework

input_container = st.container()
transcribe_col, chat_col = st.columns(2)


# Audio Tools
transcriber = transcriber_object()
transcriber.set_container(transcribe_col)


# Input Options
input_options = ['Load Audio File', 'Record Audio', 'Youtube URL']


def change_option():
    global option
    option = st.session_state.input_option
    # Clear previous chat history
    st.session_state.messages = []


if st.session_state.api_key:
    with input_container.container():
        option = st.radio(
            label='Select an Option',
            options=input_options,
            key='input_option',
            on_change=change_option,
            horizontal=True
        )

    with input_container.container():
        language = st.selectbox(
            label='Select Language',
            options=[lang for lang in Language],
            format_func=lambda x: str(x).split('.')[1],
        )

    # Upload Audio File
    if option == input_options[0]:
        with input_container.container():
            audio_file = st.file_uploader(
                "Choose a file", type=['wav', 'mp3', 'ogg'])
            if audio_file:
                # Extract file type from uploaded file
                file_type = audio_file.type.split('/')[1]

                with transcribe_col:
                    with st.spinner('Transcribing Audio...'):
                        transcriber.transcribe_free(
                            # Get bytes from Uploaded file
                            data=audio_file.getvalue(),
                            file_path='outputs/audio.'+file_type,
                            input_type=FileType.FILE,
                            language=language
                        )

    # Record Audio
    elif option == input_options[1]:
        with input_container.container():
            audio_bytes = audio_recorder(
                text="Click to Record",
                recording_color="#28B463",
                neutral_color="#E74C3C",
                icon_name="microphone",
                icon_size="3x",
                pause_threshold=300.0,

            )
            if audio_bytes:

                # Display the audio so that user can hear it
                with input_container.container():
                    st.audio(audio_bytes)

                with transcribe_col:
                    with st.spinner('Transcribing Audio...'):
                        transcriber.transcribe_free(
                            data=audio_bytes,
                            file_path='outputs/audio.wav',
                            input_type=FileType.RECORD,
                            language=language
                        )

    # Youtube Url Input
    else:
        with input_container.container():
            if youtube_url := st.text_input("Enter Youtube url", key='youtube_url'):

                with transcribe_col:
                    with st.spinner('Transcribing Audio...'):
                        transcriber.transcribe_free(
                            data=youtube_url,
                            file_path='outputs/Youtube',
                            input_type=FileType.YOUTUBE,
                            language=language
                        )

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Initialize whether to process chat input
    if "process_prompt" not in st.session_state:
        st.session_state.process_prompt = False

    # Display chat messages from history on app rerun
    with chat_col:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if transcriber.got_input and not transcriber.processing:
        st.session_state.process_prompt = False
        with chat_col:
            with st.spinner('Connecting To LLM'):
                docs = transcriber.get_docs()
                logging.debug('Transcribed Text is'+transcriber.get_text())
                try:
                    load_text(docs)
                    st.session_state.process_prompt = True
                except ValueError as e:
                    chat_col.markdown(f":red[{e}]")

    if st.session_state.process_prompt:
        if prompt := st.chat_input("Ask a question", key='chat_input'):
            with chat_col.chat_message("user"):
                st.markdown(prompt)
                st.session_state.messages.append(
                    {"role": "user", "content": prompt})

            st.session_state.process_prompt = False

            with chat_col:
                with st.spinner('The Bot is thinking...'):
                    try:
                        reply = None
                        reply = query_handler.query(prompt)
                    except ConnectionError:
                        reply = ':red[Failed to Connect]'

            with chat_col.chat_message("bot"):
                st.markdown(reply)
                st.session_state.messages.append(
                    {"role": "bot", "content": reply})
                st.session_state.process_prompt = True
