import traceback
from core.system.logger import ThreadedLoggerManager
from core.orchestrators.orchestration import OrchestrationPipeline
from setup.config_loader import ConfigLoader
from core.system.event_handler import EventQueue, process_event_async
from listen.events import EventType
import asyncio


class MainController:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)
        self.orchestration_pipeline = OrchestrationPipeline(config=self.config, logger=self.logger)
        self.event_queue = EventQueue()

    async def run_async(self, run_once=False, stop_event=None):
        while True:
            if stop_event and stop_event.is_set():
                self.logger.info("External stop signal received — exiting main loop.")
                break

            try:
                # Start STT and Event listeners in parallel
                stt_task = asyncio.create_task(
                    self.orchestration_pipeline.run_audio_input_pipeline_async()
                )
                event_task = asyncio.create_task(
                    self.orchestration_pipeline.event_queue.get()
                )

                done, _ = await asyncio.wait([stt_task, event_task], return_when=asyncio.FIRST_COMPLETED)

                if event_task in done:
                    event = event_task.result()
                    await process_event_async(event, self.orchestration_pipeline)
                    stt_task.cancel()
                    continue

                if stt_task in done:
                    user_speech_as_text, listen_obj = stt_task.result()
                    if not user_speech_as_text:
                        if run_once:
                            break
                        continue

                    # Process event from transcript
                    event_type = await self.orchestration_pipeline.process_event(user_speech_as_text)
                    if event_type.get('event_type', EventType.CONTINUE) == EventType.EMERGENCY:
                        self.logger.warning("Emergency protocol activated!")
                        # Custom emergency logic can go here
                    elif event_type.get('event_type', EventType.CONTINUE) == EventType.SLEEP:
                        user_speech_as_text, listen_obj, _ = await self.orchestration_pipeline.sleep_mode_loop()
                        continue
                    elif event_type.get('event_type', EventType.CONTINUE) == EventType.SHUTDOWN:
                        self.logger.info("Shutdown command received — exiting.")
                        break
                    elif event_type.get('event_type', EventType.CONTINUE) != EventType.CONTINUE:
                        continue

                    parsed_response, model_designation, model_config = await self.orchestration_pipeline.run_llm_pipeline(
                        user_speech_as_text
                    )
                    if not parsed_response:
                        if run_once:
                            break
                        continue

                    await self.orchestration_pipeline.llm_response_pipeline(
                        parsed_response, model_config, model_designation
                    )

                    if run_once:
                        break

            except (KeyboardInterrupt, StopIteration):
                self.logger.info("Shutdown signal received — exiting main loop.")
                break
            except Exception as main_loop_error:
                self.logger.error(f"Main loop error: {main_loop_error}\n{traceback.format_exc()}")
                if run_once:
                    break

if __name__ == "__main__":
    controller = MainController()
    asyncio.run(controller.run_async())