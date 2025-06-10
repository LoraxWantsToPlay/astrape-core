import concurrent.futures
import traceback
import asyncio

from core.models.llm_pipeline import LLMPipeline
from listen.mic_input import MicInput
from listen.events import EventManager
from speech.speech_to_text import SpeechToText
from speech.text_to_speech import TextToSpeech
from core.memory.session_memory import SessionMemoryManager
from core.system.logger import ThreadedLoggerManager
from setup.config_loader import ConfigLoader
from core.system.utils.basic_tools import BasicTools
from core.system.utils.system_tools import SystemTools
from core.system.event_handler import EventQueue
from listen.events import EventType

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))


class OrchestrationPipeline:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)
        self.llm_pipeline = LLMPipeline(config=self.config, logger=self.logger)
        self.session_memory = SessionMemoryManager(config=self.config, logger=self.logger)
        self.speech_to_text = SpeechToText(config=self.config, logger=self.logger)
        self.mic_input = MicInput(config=self.config, logger=self.logger)
        self.text_to_speech = TextToSpeech(config=self.config, logger=self.logger)
        self.system_tools = SystemTools(config=self.config, logger=self.logger)
        self.event_manager = EventManager(config=self.config, logger=self.logger)
        self.event_queue = EventQueue()
        if self.debug:
            self.logger.debug("OrchestrationPipeline initialized with debug mode ON")

    async def run_llm_pipeline(self, user_speech_as_text):
        parsed_response, model_designation, model_config = None, None, None
        model_designation = self.config['system_settings'].get('default_model_designation')
        try:
            model_config = self.config['models'].get(model_designation)
            parsed_response = await self.process_llm_call(
                user_speech_as_text,
                model_designation,
                model_config,
                append_who="user",
            )
        except Exception as e:
            self.logger.error(f"Error in LLM pipeline: {e}\n{traceback.format_exc()}")
        return parsed_response, model_designation, model_config

    async def speak_statement(self, parsed_response, model_config):
        try:
            natural_output = parsed_response.get('natural_output', False)
            if natural_output:
                await self.text_to_speech.give_text_to_speech(natural_output, model_config)
            else:
                self.logger.info("No natural output to speak.")
        except Exception as e:
            self.logger.error(f"Error in speaking statement: {e}\n{traceback.format_exc()}")

    async def speak_questions(self, parsed_response, model_config):
        try:
            confirmation = parsed_response.get('confirmation', False)
            if confirmation:
                await self.text_to_speech.give_text_to_speech(confirmation, model_config)
            else:
                self.logger.info("No confirmation to speak.")
        except Exception as e:
            self.logger.error(f"Error in speaking confirmation: {e}\n{traceback.format_exc()}")

    async def llm_response_pipeline(self, parsed_response, model_config, model_designation):
        try:
            # Run TTS and tool execution concurrently
            speak_task = asyncio.create_task(self.speak_statement(parsed_response, model_config))

            await asyncio.gather(speak_task)

            # Handle confirmations
            await self.speak_questions(parsed_response, model_config)
            
        except Exception as e:
            self.logger.error(f"Error Executing Async Response Pipeline: {e}\n{traceback.format_exc()}")

    async def llm_reprompter(self, reprompt, model_designation, model_config):
        self.logger.info(f"Reprompting with: {reprompt}")
        parsed_response = await self.process_llm_call(reprompt, model_designation, model_config, append_who="tool")
        return parsed_response

    async def process_llm_call(self, prompt, model_designation, model_config, append_who="user"):
        try:
            session_memory = self.session_memory.get_session_memory(model_designation)

            if append_who == "user":
                self.session_memory.add_to_model_memory(append_who, model_designation, prompt)
            else:
                self.logger.warning(f"Append_who is None for {model_designation}, not appending prompt to session memory.")

            response = await self.llm_pipeline.get_llm_response(prompt,session_memory,model_config)

            if response == "I'm sorry, I encountered an error while processing your request.":
                self.session_memory.append_system_to_model_memory(model_designation, response)
            else:
                self.session_memory.append_model_to_model_memory(model_designation, response)

            parsed_response = self.system_tools.parse_llm_output(response)
            return parsed_response
        except Exception as e:
            self.logger.error(f"Error during async LLM call for {model_designation}: {e}\n{traceback.format_exc()}")
            return None
    
    async def process_event(self, user_speech_as_text):
        try:
            initial_event_check = await asyncio.to_thread(
                self.event_manager.determine_event_action, user_speech_as_text
            )
            if not initial_event_check.get('matches'):
                return {'event_type': EventType.CONTINUE, 'matches': []}
            
            self.logger.info(f"{initial_event_check['event_type'].value.capitalize()} event detected.")

            return initial_event_check

        except Exception as e:
            self.logger.error(f"Error processing event: {e}\n{traceback.format_exc()}")
            return {'event_type': EventType.ERROR, 'matches': []}
  
    async def sleep_mode_loop(self):  # Asyncified sleep mode
        sleep = True
        self.logger.info("Sleep mode activated. Listening for wake word only.")
        
        while sleep: #TODO: I need to add a wake to confirm sleep if active/deactivated.
            user_speech_as_text, listen_obj = await self.run_audio_input_pipeline_async()
            if not user_speech_as_text:
                continue

            initial_event_check = await self.process_event(user_speech_as_text)

            if initial_event_check.get('event_type', EventType.CONTINUE) == EventType.EMERGENCY: #NOTE: Make the values weight hold presedence
                self.logger.info("Emergency event detected. Activating emergency protocols.")
                sleep = False
            elif initial_event_check.get('event_type', EventType.CONTINUE)  == EventType.WAKE:
                self.logger.info("Sleep mode exited: normal/wake event.")
                sleep = False
            elif initial_event_check.get('event_type', EventType.CONTINUE)  == EventType.SHUTDOWN:
                self.logger.info("Shutdown command received. Exiting sleep mode.")
                sleep = False
                exit(0)

        return user_speech_as_text, listen_obj, initial_event_check

    def set_state(self, state: str):
        self.logger.info(f"Astrape state set to: {state}")
        self.state = state  # You can later use this to skip logic while "asleep"

    async def execute_emergency_protocol(self):
        self.logger.warning("Executing emergency protocol — override in subclass if needed.")
        # You could eventually call a dedicated module or play a warning sound

    async def run_audio_input_pipeline_async(self):
        if self.debug:
            self.logger.debug("Running audio input pipeline")

        listen_obj = await asyncio.to_thread(self.mic_input.listen_with_mic)
        if not listen_obj or not listen_obj.get('audio_data'):
            self.logger.warning("No valid audio input.")
            return None, None

        user_speech_as_text = await asyncio.to_thread(self.speech_to_text.get_speech_to_text, listen_obj['wav_data'])

        await asyncio.to_thread(BasicTools().cleanup_temp_audio)

        if not user_speech_as_text:
            self.logger.info("No speech detected — skipping to next iteration.")
            return None, None

        return user_speech_as_text, listen_obj