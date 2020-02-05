from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import subprocess

from common import logger
from common.emojis import emoji_money_wings
from messengers.common import Messenger 

class Telecoda(Messenger):
    def __init__(self, token, chat_id):
        self.updater = Updater(token, use_context=True)
        self.chat_id = chat_id
        self.token = token

    """ Telegram Api """
    # if username not matched commands not worked
    def check_user(self, update):
        user = update.message.from_user
        if user.username == '<username>':
            return True
        return False

    def stop_coda(self, update, context):
        self.coda_listener.on_stop_coda_and_snark_workers()

    def set_interval(self, update):
        pass

    def send_coda(self, update, context):
        """ Send Coda """
        try:
            logger.info("Telegram", 'Sending coda...')
            # args[0] should contain recipient public key
            recipient = context.args[0]
            logger.info("Telegram", 'Recipient: {}'.format(recipient))
            # amount of coda
            amount = int(context.args[1])
            logger.info("Telegram", 'Amount: {}'.format(amount))
            fee = 5
            if len(context.args) > 2:
                fee = int(context.args[2])
                logger.info("Telegram", 'Fee: {}'.format(fee))

            if len(recipient) == 0:
                update.message.reply_text('Sorry not found recipient public key for payment')
                return
            if amount <= 0:
                update.message.reply_text('Amount should be > 0')
                return
            # here send
            payment_id = self.coda_listener.on_send_payment(recipient, amount, fee)
            update.message.reply_text('{} You successfully sent {} coda with fee: {}!\n{}'
                .format(emoji_money_wings, amount, fee, payment_id))

        except (IndexError, ValueError):
            update.message.reply_text('Usage: /send <recipient> <amount> <fee>')   

    def run(self):
        logger.info('Telegram', 'Starting telegram...')
        dp = self.updater.dispatcher
        dp.add_handler(CommandHandler("send", self.send_coda,
                                    pass_args=True,
                                    pass_chat_data=True))
        dp.add_handler(CommandHandler("stop_coda", self.stop_coda,
                                    pass_args=True,
                                    pass_chat_data=True))        
        # log all errors
        dp.add_error_handler(self.error)

        self.updater.dispatcher.add_handler(CallbackQueryHandler(self.coda_btn_listener))
        # Start the Bot
        self.updater.start_polling()
        logger.info('Telegram', 'Telegram started')

    def error(self, update, context):
        """Log Errors caused by Updates."""
        logger.info('Telegram', ('Update "%s" caused error "%s"', update, context.error)) 

    def set_coda_listener(self, coda_listener):
        self.coda_listener = coda_listener

    # button listener
    def coda_btn_listener(self, update, context):
        query = update.callback_query
        selected = query.data
        logger.info("Telegram", "Selected: {}".format(selected))
        if selected == 'Status':
            _, status = self.coda_listener.on_get_coda_status()
            self.send_message(status)
        elif selected == 'Start staking':
            _ = self.coda_listener.on_start_staking()
        elif selected == 'Start SnarkW':
            _ = self.coda_listener.on_start_snark_worker()
        elif selected == 'Stop Coda':
            self.coda_listener.on_stop_coda_and_snark_workers()
        elif selected == 'Balance':
            _ = self.coda_listener.on_get_balance()

    # buttons in string: like 'Balance' or 'Stop'
    def send_message(self, message, buttons=None):
        if buttons is None:
            self.updater.bot.send_message(self.chat_id, text=message)
        else:
            reply_markup = InlineKeyboardMarkup(self.create_buttons(buttons))
            self.updater.bot.send_message(self.chat_id, text=message, reply_markup=reply_markup) 

    def create_buttons(self, buttons):
        markup = []
        for button_label in buttons:
            markup.append(InlineKeyboardButton(button_label, callback_data=button_label))
        return [markup]

    def send_file(self, file_path):
        command = 'curl -v -F "chat_id={}" -F document=@{} https://api.telegram.org/bot{}/sendDocument'.format(self.chat_id, file_path, self.token)
        subprocess.Popen([command], stdout=subprocess.PIPE, shell = True).communicate()[0].decode("utf-8").replace("\n", "")
