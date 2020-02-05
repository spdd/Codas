from messengers.telecoda import Telecoda

def create_messenger(name, config):
    if name == 'telegram':
        return True, Telecoda(config['Telegram']['token'], config['Telegram']['chat_id'])
    else:
        return False, None