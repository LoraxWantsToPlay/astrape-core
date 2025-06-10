import asyncio
import time
from openai import AsyncOpenAI, OpenAIError
from setup.config_loader import ConfigLoader
from core.system.logger import ThreadedLoggerManager


class LLMPipeline:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)

    async def get_llm_response(self, user_input, session_chat_history, model_config):
        if not user_input:
            self.logger.warning("No user input transcript found.")
            return session_chat_history, None

        session_chat_history.append({"role": "user", "content": user_input})
        try:
            if model_config.get("stream_output", False):
                # Use streaming and collect into full response
                self.logger.debug("Using streaming LLM response.")
                chunks = []
                async for chunk in self.call_llm_api(model_config, session_chat_history):
                    chunks.append(chunk)
                response = "".join(chunks)
            else:
                self.logger.debug("Using non-streaming LLM response.")
                response = await self.call_llm_api_non_streaming(model_config, session_chat_history)

        except Exception as e:
            self.logger.error(f"Error during LLM response generation: {e}")
            response = "I'm sorry, I encountered an error while processing your request."

        return response

    async def call_llm_api_non_streaming(self, model_config, session_chat_history):
        client = AsyncOpenAI(base_url=model_config.get('node'), api_key=model_config.get('api_key'))
        model_name = model_config.get('model', 'gpt-3.5-turbo')

        self.logger.info(f"[LLM API Fallback] Using non-streamed method for '{model_name}'")

        response = await client.chat.completions.create(
            model=model_name,
            messages=session_chat_history,
            temperature=model_config.get('temperature', 0.7),
            max_tokens=model_config.get('max_tokens', 150),
            stream=False
        )
        return response.choices[0].message.content.strip()

    async def call_llm_api(self, model_config, session_chat_history, tts_handler):
        client = AsyncOpenAI(base_url=model_config.get('node'), api_key=model_config.get('api_key'))
        model_name = model_config.get('model', 'gpt-3.5-turbo')

        system_settings = self.config.get('system_settings', {})
        retry_attempts = system_settings.get('assistant_retry_attempts', 3)
        retry_delay = system_settings.get('assistant_retry_delay', 5)

        max_attempts = float('inf') if retry_attempts == 0 else retry_attempts
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                self.logger.info(f"[LLM API] Attempt {attempt} using model '{model_name}' with streaming")
                stream = await client.chat.completions.create(
                    model=model_name,
                    messages=session_chat_history,
                    temperature=model_config.get('temperature', 0.7),
                    max_tokens=model_config.get('max_tokens', 150),
                    stream=True
                )

                final_response = ""
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices[0].delta else ""
                    if delta:
                        final_response += delta
                        yield delta  # Stream this partial to whatever is listening

                self.logger.info("[LLM API] Streaming complete.")
                return  # End the generator after successful stream

            except OpenAIError as e:
                self.logger.warning(f"[LLM API] Streaming failed on attempt {attempt}: {e}")
                self.logger.info("[LLM API] Falling back to non-streaming mode")

            if attempt < max_attempts:
                delay = retry_delay * attempt
                self.logger.info(f"[LLM API] Retrying in {delay} seconds...")
                await asyncio.sleep(delay)

        self.logger.critical("[LLM API] All retry attempts failed.")
        yield "Astrape encountered an error while processing your request."

    async def stream_llm_response(self, user_input, session_chat_history, model_config, tts_handler):
        if not user_input:
            self.logger.warning("No user input transcript found.")
            return session_chat_history, None

        session_chat_history.append({"role": "user", "content": user_input})
        response = ""
        try:
            self.logger.debug("Using streaming LLM response.")
            async for token in self.call_llm_api(model_config, session_chat_history):
                response += token
                await tts_handler.handle_token(token)

        except Exception as e:
            self.logger.error(f"Error during LLM streaming: {e}")
            response = "I'm sorry, I encountered an error while processing your request."
            await tts_handler.speak(response)

        return response