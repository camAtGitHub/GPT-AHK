import keyboard
import pyperclip
import pyautogui
import time
import json
import os
import asyncio
import cerebras.cloud.sdk as AsyncCerebras
import pystray
import logging
import sys

# Set up basic console logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define initial constants
DEFAULT_HOTKEY = "win+y"
DEFAULT_MODELS = ["llama3.1-8b", "llama3.1-70b"]
available_models = []
current_model_name = "" # Global variable for the currently selected model

# --- Systray Menu Functions ---

def update_selected_model(model_name: str, icon):
    """Updates the current model and logs the change."""
    global current_model_name
    current_model_name = model_name
    logging.info(f"Model changed to: {model_name}")
    if icon:
        # This is crucial for pystray to re-render the menu and update checkmarks
        icon.update_menu()

def on_exit_clicked(icon, item):
    """Handles the Exit menu item click."""
    logging.info("Exit option clicked. Shutting down.")
    icon.stop()
    sys.exit(0)

def create_systray_menu(icon) -> pystray.Menu:
    """Creates the systray menu with dynamic model entries."""
    menu_items = []
    if not available_models:
        menu_items.append(pystray.MenuItem("No models available", None, enabled=False))
    else:
        for model_name in available_models:
            # Capture model_name by value in the lambda for action
            # The checked lambda also needs to capture model_name correctly
            menu_items.append(pystray.MenuItem(
                model_name,
                lambda _, model_n=model_name: update_selected_model(model_n, icon),
                checked=lambda _, model_n=model_name: current_model_name == model_n,
                radio=True # Makes them behave like radio buttons (only one can be checked)
            ))
    
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Exit", on_exit_clicked))
    
    return pystray.Menu(*menu_items)

def start_systray():
    """Initializes and runs the systray icon."""
    logging.info("Initializing Systray icon...")
    # Create the icon object first. pystray might use a default icon if no image is specified.
    icon = pystray.Icon("HAT-AU", title="Hotkey Text Augmentation Utility")
    
    # Create the menu, passing the icon object to it
    menu = create_systray_menu(icon)
    icon.menu = menu
    
    # Run the icon. This is a blocking call until icon.stop() or sys.exit()
    icon.run()

# --- Core Logic Functions ---

def get_selected_text() -> str | None:
    """
    Attempts to get the currently selected text by simulating a copy command.
    Restores original clipboard content if no text is selected or an error occurs.
    """
    logging.info("Attempting to get selected text...")
    original_clipboard_content = ""
    try:
        original_clipboard_content = pyperclip.paste()
        pyperclip.copy("")  # Clear clipboard to detect a new copy
        
        pyautogui.hotkey('ctrl', 'c')
        logging.info("Simulated Ctrl+C.")
        time.sleep(0.1)  # Allow OS time to process the copy command

        selected_text = pyperclip.paste()

        # Check if anything was copied. pyperclip.copy("") might result in an empty string.
        # Some systems/pyperclip versions might have a specific representation for an empty clipboard.
        # For simplicity, we assume an empty string means nothing new was copied.
        if not selected_text:
            logging.info("No text appears to be selected or copied.")
            pyperclip.copy(original_clipboard_content)  # Restore original clipboard
            return None
        else:
            logging.info(f"Selected text retrieved: '{selected_text[:100]}...'")
            # As per subtask, selected text remains on clipboard if successful for now.
            return selected_text

    except Exception as e:
        logging.error(f"Error during text selection/copying: {e}")
        try:
            pyperclip.copy(original_clipboard_content) # Attempt to restore clipboard
        except Exception as e_restore:
            logging.error(f"Failed to restore clipboard content: {e_restore}")
        return None

async def get_available_models() -> list[str]:
    """Fetches available model names from the Cerebras API."""
    client = AsyncCerebras(api_key=os.environ.get("CEREBRAS_API_KEY"))
    try:
        logging.info("Fetching available models from Cerebras API...")
        models_response = await client.models.list()
        model_names = [model.id for model in models_response.data]
        logging.info(f"Successfully fetched models: {model_names}")
        return model_names
    except Exception as e:
        logging.error(f"Error fetching models from Cerebras API: {e}")
        logging.info("Using default models.")
        return DEFAULT_MODELS
    finally:
        await client.close()
        logging.info("Cerebras client closed.")

def check_api_key():
    """Checks if the CEREBRAS_API_KEY environment variable is set."""
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        logging.error("Error: CEREBRAS_API_KEY environment variable not set.")
        print("CEREBRAS_API_KEY environment variable not set. Please set it before running the script.")
        sys.exit(1)
    else:
        logging.info("CEREBRAS_API_KEY found.")

if __name__ == "__main__":
    check_api_key()
    logging.info("Fetching available AI models...")
    available_models = asyncio.run(get_available_models())
    logging.info(f"Available models set to: {available_models}")

    if available_models:
        # Set the first model as the default selected model
        # Ensure current_model_name is updated before create_systray_menu is called via start_systray
        # update_selected_model(available_models[0], None) # icon is not available yet
        current_model_name = available_models[0] 
        logging.info(f"Default model set to: {current_model_name}")
    else:
        logging.error("No models available (neither fetched nor default). Cannot set a current model.")
        # Handling the case where no models are available - app might not be useful
        # For now, we'll let it proceed, but the menu will show "No models available"
        current_model_name = "no_model_available_placeholder" 

    # Start the systray icon. This will block the main thread.
    start_systray()
