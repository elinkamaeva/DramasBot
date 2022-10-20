import telebot
import conf
from main import find_answer

bot = telebot.TeleBot(conf.TOKEN)


# этот обработчик запускает функцию send_welcome, когда пользователь отправляет команды /start или /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id,
                     "Здравствуйте! Это бот, который обучен на корпусе драматических текстов, "
                     "который включает в себя пьесы 1740-1940 гг.\n"
                     "И он может стать для вас хорошим собеседником")

# этот обработчик запускает функцию, которая обрабатывает голосовые сообщения и отвечает на них
@bot.message_handler(content_types=['voice'])
def text_recognition(message):
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    filename = uuid.uuid4().hex
    with open(f'{filename}.ogg', 'wb') as new_file:
        new_file.write(downloaded_file)

    ogg_version = AudioSegment.from_ogg(f"{filename}.ogg")
    ogg_version.export(f"{filename}.wav", format="wav")

    user_audio_file = sr.AudioFile(f"{filename}.wav")
    with user_audio_file as source:
        user_audio = r.record(source)
    text = r.recognize_google(user_audio, language='ru')

    os.remove(f"{filename}.wav")
    os.remove(f"{filename}.ogg")

    bot.send_message(message.chat.id, find_answer(text))


# этот обработчик запускает функцию, которая обрабатывает сообщения и отвечает на них
@bot.message_handler(content_types=['text'])
def send_len(message):
    bot.send_message(message.chat.id, find_answer(message.text))


if __name__ == "__main__":
    bot.polling(none_stop=True)
