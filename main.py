import telebot
from telebot import types
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
import threading
import re

# === НАСТРОЙКИ ===
BOT_TOKEN = '7640880064:AAEOqKU4mWP06Ob96K3h4VDfrIhfK164Eg0'
GOOGLE_SHEET = 'DocExpress_Заявки'
ADMIN_CHAT_ID = 5780051172

# === ДОСТУП К GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET).sheet1

# === ИНИЦИАЛИЗАЦИЯ ===
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
user_states = {}

# === СТАДИИ ===
stages = ['name', 'phone', 'email', 'doc_type', 'task', 'complete']

doc_types = [
    "📝 Договор",
    "🧾 Жалоба",
    "📬 Заявление",
    "📄 Претензия",
    "📋 Акт",
    "📎 Другое"
]

# === ВАЛИДАЦИЯ ===
def is_valid_phone(phone):
    return re.match(r'^\+?7\d{10}$', phone)

def is_valid_email(email):
    return re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email)

# === СТАРТ ===
@bot.message_handler(commands=['start'])
def start(message):
    user_states[message.chat.id] = {'stage': 'name'}
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать!\n\n"
        "Я — цифровой помощник по оформлению документов.\n"
        "Сейчас я задам несколько вопросов, чтобы подготовить всё грамотно и в срок.\n\n"
        "📌 Поехали. Как вас зовут?"
    )

# === ДИАЛОГ ===
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    cid = message.chat.id
    if cid not in user_states:
        user_states[cid] = {'stage': 'name'}

    state = user_states[cid]
    stage = state['stage']
    text = message.text.strip()

    if stage == 'name':
        state['name'] = text
        state['stage'] = 'phone'
        bot.send_message(cid, "📱 Укажите, пожалуйста, ваш номер телефона в формате +7XXXXXXXXXX:")
    
    elif stage == 'phone':
        if not is_valid_phone(text):
            bot.send_message(cid, "❌ Пожалуйста, введите корректный номер: +7XXXXXXXXXX")
            return
        state['phone'] = text
        state['stage'] = 'email'
        bot.send_message(cid, "📧 Укажите ваш email для отправки готового документа:")
    
    elif stage == 'email':
        if not is_valid_email(text):
            bot.send_message(cid, "❌ Пожалуйста, введите корректный email.")
            return
        state['email'] = text
        state['stage'] = 'doc_type'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for doc in doc_types:
            markup.add(types.KeyboardButton(doc))
        bot.send_message(cid, "📂 Выберите тип документа, который хотите оформить:", reply_markup=markup)
    
    elif stage == 'doc_type':
        state['doc_type'] = text
        state['stage'] = 'task'
        bot.send_message(cid, "✍️ Пожалуйста, опишите суть задачи, включая:\n"
                              "— для кого документ\n— по какому вопросу\n— и что важно учесть.")
    
    elif stage == 'task':
        state['task'] = text
        state['stage'] = 'complete'
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Добавим в Google Таблицу
        sheet.append_row([now, state['name'], state['phone'], state['email'], state['doc_type'], state['task'], ""])

        # Уведомим Админа
        msg = (
            f"📥 Новая заявка:\n"
            f"👤 Имя: {state['name']}\n"
            f"📱 Телефон: {state['phone']}\n"
            f"📧 Email: {state['email']}\n"
            f"📄 Тип: {state['doc_type']}\n"
            f"📝 Задача: {state['task']}"
        )
        bot.send_message(ADMIN_CHAT_ID, msg)

        # Ответ клиенту
        bot.send_message(cid, "✅ Спасибо! Все данные получены.\n"
                              "📂 Ваш документ будет готов в течение 15–30 минут.\n"
                              "Если будут уточнения — мы свяжемся.")

    else:
        bot.send_message(cid, "❗ Пожалуйста, начните заново: /start")
        user_states[cid] = {'stage': 'name'}

# === FLASK-SERVER ===
@app.route('/', methods=['GET'])
def index():
    return "Бот работает!"

@app.route('/', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return '', 200

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# === ЗАПУСК ===
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    print("Бот запущен...")
    bot.remove_webhook()
    bot.set_webhook(url="https://flask-hello-world.onrender.com")  # ← Укажи свой Render URL
