# main.py (бот с валидацией телефона и умным диалогом)
from flask import Flask, request
import telegram
from telegram.ext import Dispatcher, MessageHandler, Filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import phonenumbers

app = Flask(__name__)

TOKEN = "ВАШ_ТОКЕН"
bot = telegram.Bot(token=TOKEN)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("DocRequests").sheet1

dispatcher = Dispatcher(bot, update_queue=None, use_context=True)

def validate_phone(text):
    try:
        phone = phonenumbers.parse(text, "RU")
        return phonenumbers.is_valid_number(phone)
    except:
        return False

def handle_message(update, context):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    if validate_phone(user_text):
        sheet.append_row([str(chat_id), user_text])
        bot.send_message(chat_id=chat_id, text="Спасибо! Ваш номер принят. Мы скоро свяжемся с вами.")
    else:
        bot.send_message(chat_id=chat_id, text="Пожалуйста, отправьте ваш номер телефона для связи.")

dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"