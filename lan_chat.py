# -*- coding: utf-8 -*-

# Import necessary libraries
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import customtkinter as ctk
import socket
import threading
import json
import base64
import os
import io
from PIL import Image, ImageTk, ImageDraw
import requests
import re
from urllib.parse import urlparse

# Set a persistent chat ID to prevent message loops
# and identify messages from this specific instance.
# This should be unique for each running instance.
import uuid
CHAT_ID = str(uuid.uuid4())

# --- Configuration Constants ---
MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5007
PROFILE_PIC_SIZE = (64, 64)
MAX_IMAGE_SIZE_KB = 40  # 40 KB limit for locally attached images

# Initialize CustomTkinter with a dark theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# User settings file to save username and profile picture path
SETTINGS_FILE = "user_settings.json"

# Regex pattern to detect image URLs
IMAGE_URL_PATTERN = re.compile(r'^(https?://.*\.(?:png|jpg|jpeg|gif))$')

class ChatApp:
    def __init__(self, root):
        """Initializes the main application window and components."""
        self.root = root
        self.root.title("MaxChat")

        # Load or create user settings
        self.username = "User"
        self.profile_pic_path = None
        self.load_settings()

        # Set up a dictionary to store received profile pictures to avoid
        # reloading and flickering. Key is the username, value is the PhotoImage.
        self.profile_pic_cache = {}

        # The main frame to hold all widgets
        self.main_frame = ctk.CTkFrame(self.root, fg_color="#1e1e1e")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Top Section: Chat log and Buttons ---
        self.top_frame = ctk.CTkFrame(self.main_frame, fg_color="#1e1e1e")
        self.top_frame.pack(fill="x", pady=(0, 10))

        # Title Label
        self.title_label = ctk.CTkLabel(self.top_frame, text="MaxChat", font=("Inter", 20, "bold"))
        self.title_label.pack(side="left", padx=(0, 10))

        # Settings Button
        self.settings_button = ctk.CTkButton(self.top_frame, text="Settings", command=self.open_settings)
        self.settings_button.pack(side="right", padx=(0, 10))
        
        # Embedded Image Button
        self.image_button = ctk.CTkButton(self.top_frame, text="Attach Local Image", command=self.select_image_to_embed)
        self.image_button.pack(side="right", padx=(0, 10))
        
        # --- Middle Section: Chat Display ---
        # Chat log display
        self.chat_display = scrolledtext.ScrolledText(self.main_frame, wrap=tk.WORD, state=tk.DISABLED,
                                                      font=("Inter", 12),
                                                      background="#252526", foreground="#d4d4d4",
                                                      insertbackground="#d4d4d4")
        self.chat_display.tag_config('username', foreground="#569cd6", font=("Inter", 12, "bold"))
        self.chat_display.tag_config('info', foreground="#9cd69c", font=("Inter", 10, "italic"))
        self.chat_display.pack(fill="both", expand=True)

        # --- Bottom Section: Message Input ---
        self.input_frame = ctk.CTkFrame(self.main_frame)
        self.input_frame.pack(fill="x", pady=(10, 0))

        # Message Entry
        self.message_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type message or paste an image URL...",
                                          font=("Inter", 12))
        self.message_entry.bind("<Return>", lambda event: self.send_message())
        self.message_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Send Button
        self.send_button = ctk.CTkButton(self.input_frame, text="Send", command=self.send_message)
        self.send_button.pack(side="right")

        # Initialize network components
        self.sock = None
        self.setup_multicast_socket()

        # Start listening for messages in a separate thread
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()

        # Reference to the image to embed
        self.image_to_embed = None
        
        # Initial message to show the app has started
        self.display_message("App Info", "Chat client started. You can now send and receive messages on the LAN.")
        
    def load_settings(self):
        """Loads user settings from a JSON file."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.username = settings.get("username", "User")
                    self.profile_pic_path = settings.get("profile_pic_path")
            except (IOError, json.JSONDecodeError):
                self.username = "User"
                self.profile_pic_path = None

    def save_settings(self):
        """Saves user settings to a JSON file."""
        settings = {
            "username": self.username,
            "profile_pic_path": self.profile_pic_path
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)

    def open_settings(self):
        """Creates and displays the settings window."""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("300x250")
        settings_window.resizable(False, False)
        settings_window.attributes("-topmost", True)

        ctk.CTkLabel(settings_window, text="Username:").pack(pady=(10, 5))
        username_entry = ctk.CTkEntry(settings_window, placeholder_text=self.username)
        username_entry.insert(0, self.username)
        username_entry.pack(pady=5)

        ctk.CTkLabel(settings_window, text="Profile Picture:").pack(pady=(10, 5))
        pic_button = ctk.CTkButton(settings_window, text="Select Picture", command=lambda: self.select_profile_pic(pic_button))
        pic_button.pack(pady=5)

        def save():
            """Saves changes and closes the settings window."""
            new_username = username_entry.get()
            if new_username:
                self.username = new_username
            self.save_settings()
            settings_window.destroy()

        save_button = ctk.CTkButton(settings_window, text="Save", command=save)
        save_button.pack(pady=20)

    def select_profile_pic(self, button):
        """Opens a file dialog to select a profile picture."""
        path = filedialog.askopenfilename(
            title="Select Profile Picture",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )
        if path:
            self.profile_pic_path = path
            button.configure(text=os.path.basename(path))

    def select_image_to_embed(self):
        """Opens a file dialog to select an image to embed in a message."""
        path = filedialog.askopenfilename(
            title="Select Local Image to Embed",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )
        if path:
            # Check the file size before proceeding
            file_size_kb = os.path.getsize(path) / 1024
            if file_size_kb > MAX_IMAGE_SIZE_KB:
                messagebox.showerror("Image Too Large",
                                     f"Image size must be less than {MAX_IMAGE_SIZE_KB} KB. "
                                     f"Selected image is {file_size_kb:.2f} KB.")
                self.image_to_embed = None
                return

            self.image_to_embed = path
            messagebox.showinfo("Image Selected", "Local image ready to be sent with your next message.")

    def setup_multicast_socket(self):
        """Sets up the UDP socket for multicast communication."""
        try:
            # Create a UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

            # Set the time-to-live for multicast packets to 1 so they don't leave the local network
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

            # Allow reuse of the address, which is sufficient for our purposes
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to the multicast port
            self.sock.bind(('', MULTICAST_PORT))

            # Tell the operating system to add the socket to the multicast group on all network interfaces
            mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton('0.0.0.0')
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        except Exception as e:
            messagebox.showerror("Network Error", f"Failed to set up multicast socket: {e}")
            self.root.destroy()
            return False
        return True

    def get_profile_pic_base64(self):
        """Loads, resizes, crops into a circle, and base64-encodes the profile picture."""
        if not self.profile_pic_path or not os.path.exists(self.profile_pic_path):
            return None
        
        try:
            # Open and resize the image
            img = Image.open(self.profile_pic_path)
            img = img.resize(PROFILE_PIC_SIZE, Image.Resampling.LANCZOS)
            
            # Create a circular mask
            mask = Image.new('L', PROFILE_PIC_SIZE, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + PROFILE_PIC_SIZE, fill=255)

            # Apply the mask to the image
            img.putalpha(mask)

            # Convert to a byte stream and base64 encode
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return img_str
        except Exception as e:
            print(f"Error encoding profile picture: {e}")
            return None
            
    def send_message(self):
        """Sends a message over the network, handling text, local images, and image URLs."""
        message = self.message_entry.get()
        payload = {
            'chat_id': CHAT_ID,
            'username': self.username,
            'profile_pic': self.get_profile_pic_base64(),
            'text': None,
            'image_type': None,
            'image_content': None,
        }

        # Check for image URL
        image_match = IMAGE_URL_PATTERN.match(message)
        if image_match:
            payload['image_type'] = "url"
            payload['image_content'] = message
        else:
            # Check for a locally attached image
            if self.image_to_embed and os.path.exists(self.image_to_embed):
                try:
                    with open(self.image_to_embed, "rb") as f:
                        img_data = f.read()
                    
                    payload['image_type'] = "data"
                    payload['image_content'] = base64.b64encode(img_data).decode('utf-8')
                except Exception as e:
                    self.display_message("Error", f"Failed to attach local image: {e}", "info")
                    return # Exit if local image fails to attach
            
            # If no image is attached, send a text message
            elif message.strip():
                payload['text'] = message

        # If no content, do nothing
        if not payload['text'] and not payload['image_content']:
            return
        
        # Display the message to the sender locally before sending it
        self.display_received_message(payload)

        try:
            data = json.dumps(payload).encode('utf-8')
            self.sock.sendto(data, (MULTICAST_GROUP, MULTICAST_PORT))
            self.message_entry.delete(0, tk.END)
            # Reset the local image to embed after sending
            self.image_to_embed = None 
        except Exception as e:
            self.display_message("Error", f"Failed to send message: {e}", "info")

    def receive_messages(self):
        """Listens for and displays incoming messages."""
        while True:
            try:
                data, addr = self.sock.recvfrom(65536)  # Buffer size
                message_data = json.loads(data.decode('utf-8'))
                
                # Prevent displaying messages sent from this instance
                if message_data['chat_id'] == CHAT_ID:
                    continue

                self.display_received_message(message_data)
                
            except Exception as e:
                # This could be a decoding error or socket error
                print(f"Error receiving message: {e}")
                
    def display_received_message(self, message_data):
        """Formats and displays a received message in the chat log."""
        username = message_data.get('username', 'Unknown')
        text = message_data.get('text', '')
        profile_pic_base64 = message_data.get('profile_pic')
        image_type = message_data.get('image_type')
        image_content = message_data.get('image_content')

        self.chat_display.configure(state=tk.NORMAL)
        
        # Display profile picture
        if profile_pic_base64:
            if username not in self.profile_pic_cache:
                try:
                    img_data = base64.b64decode(profile_pic_base64)
                    pil_img = Image.open(io.BytesIO(img_data))
                    profile_pic = ImageTk.PhotoImage(pil_img)
                    self.profile_pic_cache[username] = profile_pic
                except Exception as e:
                    print(f"Error decoding profile picture for {username}: {e}")
                    self.profile_pic_cache[username] = None
            
            if self.profile_pic_cache.get(username):
                self.chat_display.image_create(tk.END, image=self.profile_pic_cache[username], padx=5, pady=5)
            
        # Display username
        self.chat_display.insert(tk.END, f"\n{username}: ", 'username')
        
        # Display the message text
        if text:
            self.chat_display.insert(tk.END, text + "\n")

        # Display embedded images based on type
        if image_type == "data":
            # Display locally attached image
            try:
                img_data = base64.b64decode(image_content)
                pil_img = Image.open(io.BytesIO(img_data))
                self.display_image_in_chat(pil_img)
            except Exception as e:
                print(f"Error decoding embedded image data: {e}")
                self.display_message("Image Error", "Could not display image.", "info")
        
        elif image_type == "url":
            # Download and display the image from URL in a separate thread
            self.display_message("Info", "Downloading image from URL...", "info")
            threading.Thread(target=self.download_and_display_url_image, args=(image_content,), daemon=True).start()
                
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.yview_moveto(1.0) # Scroll to the bottom
    
    def download_and_display_url_image(self, url):
        """Downloads an image from a URL and displays it in the chat."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            img_data = response.content
            pil_img = Image.open(io.BytesIO(img_data))
            
            # Use the main thread to update the GUI
            self.root.after(0, self.display_image_in_chat, pil_img)
            
        except requests.exceptions.RequestException as e:
            # Notify the user of the download failure
            self.display_message("URL Error", f"Failed to download image from URL: {e}", "info")
        except Exception as e:
            self.display_message("Image Error", f"Could not display image from URL: {e}", "info")
            
    def display_image_in_chat(self, pil_img):
        """Inserts a PIL Image into the chat widget on the main thread."""
        # Resize image for display if it's too large, but maintain aspect ratio
        max_width = 300
        max_height = 300
        pil_img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Store a reference to the image to prevent garbage collection
        embedded_image = ImageTk.PhotoImage(pil_img)
        self.chat_display.image_create(tk.END, image=embedded_image, padx=5, pady=5)
        self.chat_display.image_refs = getattr(self.chat_display, 'image_refs', [])
        self.chat_display.image_refs.append(embedded_image)
        self.chat_display.insert(tk.END, "\n") # Newline after image

    def display_message(self, source, message, tag=None):
        """Displays a simple text message in the chat log."""
        self.chat_display.configure(state=tk.NORMAL)
        if tag:
            self.chat_display.insert(tk.END, f"[{source}]: {message}\n", tag)
        else:
            self.chat_display.insert(tk.END, f"[{source}]: {message}\n")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.yview_moveto(1.0)

if __name__ == "__main__":
    try:
        root = ctk.CTk()
        app = ChatApp(root)
        root.mainloop()
    except Exception as e:
        print(f"An error occurred: {e}")

