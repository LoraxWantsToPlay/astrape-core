import re
import json
import concurrent.futures

from setup.config_loader import ConfigLoader
from core.system.logger import ThreadedLoggerManager

class SystemTools:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)
        
        self.model_config = self.config['models']

    def get_words(self, word_type: str):
        words = []
        try:
            for model in self.model_config:
                if self.model_config[model].get('enabled') and self.model_config[model].get(word_type):
                    value = self.model_config[model][word_type]
                    # Ensure value is iterable and not nested
                    if not isinstance(value, str):
                        for item in value:
                            words.append(str(item))
                    else:
                        words.append(value)
                    if self.debug:
                        self.logger.debug(f"Loaded {word_type}: {words}")
        except Exception as e:
            self.logger.error(f"Error getting words for type {word_type}: {e}")
        return words

    def get_wake_words(self): return self.get_words('wake_phrases')
    def get_sleep_words(self): return self.get_words('sleep_phrases')
    def get_emergency_words(self): return self.get_words('emergency_phrases')
    def get_shutdown_words(self): return self.config['system_settings'].get('immediate_halt_phrases', [])

    def get_available_roles(self):
        roles = set()
        try:
            for model in self.model_config:
                if self.model_config[model].get('enabled'):
                    roles.update(self.model_config[model].get('roles', []))
        except Exception as e:
            self.logger.error(f"Error getting available roles: {e}")
        return roles

    def get_roles(self):
        return list(self.config.get('roles', {}).keys())

    def get_role_keywords(self, role: str):
        return self.config['roles'].get(role, {}).get("key_words", [])

    def get_available_tools(self):
        tools = []
        try:
            if self.config['tools'].get('enabled', False):
                tools.extend(self.config["tools"].get("allowed_tools", []))
        except Exception as e:
            self.logger.error(f"Error getting available tools: {e}")
        return tools

    def classify_intent(self, text: str):
        default_role = "conversation"
        text = text.lower()
        try:
            for role in self.get_available_roles():
                for keyword in self.get_role_keywords(role):
                    if keyword in text:
                        return role
        except Exception as e:
            self.logger.warning(f"Intent classification fallback to default due to error: {e}")
        return default_role

    def get_all_models(self):
        return [self.model_config[model].get('designation') for model in self.model_config]

    def get_available_models(self):
        return [self.model_config[model].get('designation') for model in self.model_config if self.model_config[model].get('enabled', False)]

    def get_model_based_on_role(self, role: str):
        try:
            config = self.config
            candidates = [config['system_settings'].get('default_model_designation', 'model_1')]
            best_score = 0
            for model in self.get_available_models():
                model_attrs = self.model_config[model].get('roles', {})
                score = model_attrs.get(role, 0)
                if score > best_score:
                    candidates = [model]
                    best_score = score
                elif score == best_score:
                    candidates.append(model)
            return candidates
        except Exception as e:
            self.logger.error(f"Error selecting model for role {role}: {e}")
            return []

    def get_roles_of_model(self, model):
        return list(self.model_config.get(model, {}).get('roles', []))

    def generate_system_prompt_for_model(self, model):
        try:
            roles = self.get_roles_of_model(model)
            current_model = self.model_config[model]
            prompt = f"You are {current_model['name']}, a specialized AI agent."
            return prompt
        except Exception as e:
            self.logger.error(f"Error generating system prompt: {e}")
            return ""

    def parse_llm_output(self, response):
        try:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                natural_output_future = pool.submit(self.extract_natural_output, response)
                confirmation_future = pool.submit(self.extract_confirmation, response)
                natural_output = natural_output_future.result()
                confirmation = confirmation_future.result()

                # Strip confirmation line from the natural output only if it's distinct and at the end
                if confirmation and confirmation in natural_output:
                    lines = natural_output.splitlines()
                    filtered_lines = [line for line in lines if line.strip() != confirmation]
                    natural_output = '\n'.join(filtered_lines).strip()

                return {
                    'tool_calls': None,
                    'natural_output': natural_output,
                    'confirmation': confirmation,
                }

        except Exception as e:
            self.logger.error(f"Error in concurrent response processing: {e}")
            return None


    def extract_natural_output(self, response):
        try:
            # Remove all known code blocks
            cleaned = re.sub(r'```json\s*{.*?}\s*```', '', response, flags=re.DOTALL)
            cleaned = re.sub(r'```(?:text)?\s*.*?```', '', cleaned, flags=re.DOTALL)
            return cleaned.strip()
        except Exception as e:
            self.logger.warning(f"Error extracting natural output: {e}")
            return ""

    def extract_confirmation(self, response):
        try:
            confirmation_keywords = [
                "Do you want", "Should I", "Would you like", "Shall I",
                "Can I", "May I", "Are you sure", "Confirm", "Please confirm", "Is that okay",
            ]
            for line in reversed(response.strip().splitlines()):
                stripped = line.strip()
                if not stripped or not stripped.endswith("?"):
                    continue
                if any(keyword.lower() in stripped.lower() for keyword in confirmation_keywords):
                    return stripped
            return None
        except Exception as e:
            self.logger.warning(f"Error extracting confirmation: {e}")
            return None



    def authenticate_action(self, users=None, credentials={}):
        try:
            if users and credentials.get('user') in users:
                return True
        except Exception as e:
            self.logger.warning(f"Error in authentication logic: {e}")
        return False

    def get_user_authentication(self, reason):
        try:
            users = self.get_users_from_group(self.get_group_from_tool(reason))
            return self.authenticate_action(users, self.get_credentials())
        except Exception as e:
            self.logger.warning(f"Error getting user authentication: {e}")
            return False

    def get_credentials(self):
        try:
            return {
                'user': input("Username: ").strip().lower(),
                'password': input("Password: ").strip()
            }
        except Exception as e:
            self.logger.warning(f"Error collecting credentials: {e}")
            return {}

    def get_group_from_tool(self, tool):
        try:
            tool_category = self.config['tool_registry'][tool[0]['category']]
            for option in tool_category:
                if tool[0]['tool'] == option['name']:
                    return option['access_control'].get('groups', [])
        except Exception as e:
            self.logger.warning(f"Error getting group from tool: {e}")
        return []

    def get_users_from_group(self, groups):
        users = []
        try:
            group_registry = self.config['user_groups']
            for group in groups:
                users.extend(group_registry.get(group, {}).get('users', []))
        except Exception as e:
            self.logger.warning(f"Error getting users from group: {e}")
        return users

    def safe_append_message(self, content):
        if not isinstance(content, str):
            self.logger.warning(f"Auto-converting message to string due to type {type(content)}")
            content = str(content)
        return content