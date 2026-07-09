import os
import io
import re
import logging
from PIL import Image
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import validators

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

# Supported image formats
SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'gif']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    welcome_text = """
🎉 Welcome to **CoolConverter5Bot**!

I can help you with:
🖼️ **Image Converter** - Convert images to different formats
🔗 **URL Shortener** - Shorten long URLs instantly
📊 **Word Counter** - Count words, characters, and sentences

Commands:
/convert - Convert an image (send me an image first)
/shorten - Shorten a URL (send me a link first)
/count - Count words in text (send me text first)
/help - Show this message again

Just send me an image, URL, or text and I'll suggest actions!
    """
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    await start(update, context)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image messages and show conversion options."""
    photo = update.message.photo[-1]
    file = await photo.get_file()
    
    # Download image data
    image_data = await file.download_as_bytearray()
    
    # Store in context for later use
    context.user_data['image_data'] = image_data
    
    # Create inline keyboard with format options
    keyboard = []
    row = []
    for i, fmt in enumerate(SUPPORTED_FORMATS):
        row.append(InlineKeyboardButton(fmt.upper(), callback_data=f"convert_{fmt}"))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🖼️ What format would you like to convert this image to?",
        reply_markup=reply_markup
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages and detect if it's a URL or text for counting."""
    text = update.message.text
    
    # Check if it's a URL
    if validators.url(text):
        context.user_data['url'] = text
        keyboard = [
            [InlineKeyboardButton("🔗 Shorten URL", callback_data="shorten_url")],
            [InlineKeyboardButton("📊 Count Words in URL", callback_data="count_url")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🔗 I detected a URL! What would you like to do?",
            reply_markup=reply_markup
        )
    else:
        # Count words in text
        context.user_data['text'] = text
        await show_word_count(update.message, text)

async def show_word_count(message, text):
    """Show word count statistics for text."""
    # Count words
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)
    
    # Count characters (including spaces)
    char_count = len(text)
    char_no_spaces = len(text.replace(' ', ''))
    
    # Count sentences
    sentences = re.split(r'[.!?]+', text)
    sentence_count = len([s for s in sentences if s.strip()])
    
    # Count paragraphs
    paragraphs = text.split('\n\n')
    paragraph_count = len([p for p in paragraphs if p.strip()])
    
    result = f"""
📊 **Word Count Results**

📝 Words: {word_count}
📖 Characters (with spaces): {char_count}
✏️ Characters (without spaces): {char_no_spaces}
📄 Sentences: {sentence_count}
📑 Paragraphs: {paragraph_count}

Want me to shorten a URL too? Just send me a link!
    """
    await message.reply_text(result, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("convert_"):
        # Image conversion
        format_type = data.replace("convert_", "")
        if format_type == 'jpg':
            format_type = 'jpeg'
        
        image_data = context.user_data.get('image_data')
        if not image_data:
            await query.edit_message_text("❌ No image found. Please send an image first.")
            return
        
        try:
            # Convert image using PIL
            img = Image.open(io.BytesIO(image_data))
            
            # Handle RGBA to RGB for JPEG
            if format_type == 'jpeg' and img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Save to bytes
            output = io.BytesIO()
            img.save(output, format=format_type)
            output.seek(0)
            
            # Send the converted image
            await query.edit_message_text("✅ Converting image...")
            await query.message.reply_document(
                document=output,
                filename=f"converted.{format_type}",
                caption=f"🖼️ Image converted to {format_type.upper()}"
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error converting image: {str(e)}")
    
    elif data == "shorten_url":
        # URL shortening
        url = context.user_data.get('url')
        if not url:
            await query.edit_message_text("❌ No URL found. Please send a URL first.")
            return
        
        try:
            # Using spoo.me as a free URL shortener
            response = requests.post(
                "https://spoo.me/",
                data={"url": url},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                short_url = response.json().get('short_url')
                await query.edit_message_text(
                    f"🔗 **Shortened URL**\n\n"
                    f"Original: {url}\n"
                    f"Shortened: {short_url}\n\n"
                    f"✅ Click the link above to visit the shortened URL!"
                )
            else:
                await query.edit_message_text("❌ Failed to shorten URL. Please try again.")
                
        except Exception as e:
            await query.edit_message_text(f"❌ Error shortening URL: {str(e)}")
    
    elif data == "count_url":
        # Count words in URL content (simplified version)
        url = context.user_data.get('url')
        if not url:
            await query.edit_message_text("❌ No URL found. Please send a URL first.")
            return
        
        await query.edit_message_text("📊 Analyzing URL content...")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Extract text from HTML (very basic)
                text = response.text
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                # Remove extra whitespace
                text = re.sub(r'\s+', ' ', text)
                
                await show_word_count(query.message, text.strip())
            else:
                await query.edit_message_text("❌ Could not access the URL. Please check the link.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error analyzing URL: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document (image) messages."""
    document = update.message.document
    if document.mime_type and document.mime_type.startswith('image/'):
        # It's an image document
        file = await document.get_file()
        image_data = await file.download_as_bytearray()
        context.user_data['image_data'] = image_data
        
        # Create inline keyboard with format options
        keyboard = []
        row = []
        for i, fmt in enumerate(SUPPORTED_FORMATS):
            row.append(InlineKeyboardButton(fmt.upper(), callback_data=f"convert_{fmt}"))
            if (i + 1) % 3 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🖼️ What format would you like to convert this image to?",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Please send an image file or photo for conversion.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.warning(f"Update {update} caused error {context.error}")

def main():
    """Start the bot."""
    # Create Application
    app = Application.builder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Callback query handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
