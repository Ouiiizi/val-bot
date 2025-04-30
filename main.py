import threading
import web_login  
import bot       

def run_flask():
    web_login.app.run(port=5000, use_reloader=False)

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Start the Discord bot (this will block the main thread)
    bot.run_bot()
