import telebot
from telebot import types
import datetime
import re
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from docx import Document
from flask import Flask, request
import threading

BOT_TOKEN = '7640880064:AAEOqKU4mWP06Ob96K3h4VDfrIhfK164Eg0'
ADMIN_ID = 5780051172
SHEET_NAME = "DocExpress_Заявки"

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}
current_step = {}
current_type = {}

# === Google Таблицы ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# === Сценарии ===
scenarios = {
    "Договор подряда": [
        "Как зовут заказчика?",
        "Как зовут исполнителя?",
        "Какие работы нужно выполнить?",
        "До какой даты нужно всё сделать?",
        "Сколько вы договорились за работу?",
        "Укажите номер телефона для связи"
    ],
    "Жалоба в УК": [
        "На каком адресе произошла проблема?",
        "Что произошло? (опишите ситуацию своими словами)",
        "Когда это случилось?",
        "Есть ли у вас доказательства? (фото/видео)",
        "Оставьте номер телефона для связи"
    ],
    "Заявление в суд": [
        "Кто подаёт заявление (ваше ФИО)?",
        "Против кого подаёте заявление (ФИО ответчика)?",
        "Что произошло? Расскажите суть конфликта простыми словами.",
        "Что вы хотите, чтобы суд решил?",
        "Укажите ваш номер телефона"
    ],
    "Претензия продавцу": [
        "Где и что вы купили?",
        "Что случилось с товаром/услугой?",
        "Как вы хотите решить этот вопрос? (например: возврат, замена, ремонт)",
        "Номер телефона для связи"
    ],
    "Акт выполненных работ": [
        "Кто заказывает работу? (ФИО или организация)",
        "Кто выполняет работу? (ФИО или организация)",
        "Что именно было сделано?",
        "Когда была завершена работа?",
        "Ваш номер телефона"
    ],
    "Доверенность": [
        "Кто доверяет? (ФИО)",
        "Кому доверяет? (ФИО)",
        "На какие действия даётся доверенность?",
        "На какой срок?",
        "Ваш телефон"
    ],
    "Заявление о прописке": [
        "Кто подаёт заявление (ФИО)?",
        "Кого нужно прописать (ФИО)?",
        "Какой адрес прописки?",
        "Контактный номер телефона"
    ]
}

def generate_docx(doc_type, answers):
    doc = Document()
    doc.add_heading(doc_type, 0)
    for i, (q, a) in enumerate(answers, 1):
        doc.add_paragraph(f"{i}. {q}")
        doc.add_paragraph(f"   ➤ {a}", style='List Bullet')
    filename = f"{doc_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    filepath = f"/tmp/{filename}"
    doc.save(filepath)
    return filepath

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for key in scenarios.keys():
        markup.add(types.KeyboardButton(key))
    bot.send_message(message.chat.id, "👋 Привет! Я Оформлятор — юридический помощник.\n\nВыберите тип документа или опишите задачу:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in scenarios.keys())
def start_scenario(message):
    chat_id = message.chat.id
    current_type[chat_id] = message.text
    current_step[chat_id] = 0
    user_data[chat_id] = []
    bot.send_message(chat_id, scenarios[message.text][0])

@bot.message_handler(func=lambda msg: msg.chat.id in current_step)
def handle_response(message):
    chat_id = message.chat.id
    step = current_step[chat_id]
    scenario = scenarios[current_type[chat_id]]
    user_data[chat_id].append((scenario[step], message.text))
    step += 1
    if step < len(scenario):
        current_step[chat_id] = step
        bot.send_message(chat_id, scenario[step])
    else:
        bot.send_message(chat_id, "Проверьте, всё ли верно 👇")
        for q, a in user_data[chat_id]:
            bot.send_message(chat_id, f"{q}\n➤ {a}")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("✅ Да", "❌ Нет")
        bot.send_message(chat_id, "Отправить этот документ?", reply_markup=markup)
        current_step.pop(chat_id)

@bot.message_handler(func=lambda msg: msg.text in ["✅ Да", "❌ Нет"])
def confirm_send(message):
    chat_id = message.chat.id
    if message.text == "✅ Да":
        doc_type = current_type[chat_id]
        answers = user_data[chat_id]
        filepath = generate_docx(doc_type, answers)

        with open(filepath, "rb") as doc_file:
            bot.send_document(chat_id, doc_file)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet.append_row([now, chat_id, doc_type] + [a for _, a in answers])

        user = message.from_user
        summary = f"📬 Новая заявка от @{user.username or 'Без ника'}\n\nТип: {doc_type}\n"
        for q, a in answers:
            summary += f"\n{q}\n➤ {a}"
        bot.send_message(ADMIN_ID, summary)

        bot.send_message(chat_id, "✅ Документ отправлен. Спасибо! Мы свяжемся при необходимости.")
    else:
        bot.send_message(chat_id, "❌ Ок, начнём заново. Выберите тип документа.")
        start(message)

# === Обработка голосовых сообщений ===
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    bot.send_message(message.chat.id, "⚠️ Я пока не умею распознавать голосовые. Напишите, пожалуйста, текстом 🙏")

# === Обработка вложений ===
@bot.message_handler(content_types=['document', 'photo'])
def handle_files(message):
    bot.send_message(message.chat.id, "🗂 Файл получен. Но пока загрузка файлов доступна только для администратора. Напишите, что нужно.")

# === Flask-сервер для Webhook ===
app = Flask(__name__)

@app.route('/')
def index():
    return "Бот активен."

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"), bot)
    bot.process_new_updates([update])
    return 'ok', 200

# === Запуск ===
if __name__ == '__main__':
    import os
    bot.remove_webhook()
    bot.set_webhook(url=f"https://flask-hello-world-<твоя-ссылка>.onrender.com/{BOT_TOKEN}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
