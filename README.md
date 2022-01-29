# GM/GN Bot

Discord bot that reacts to "gm" with a "sun" and "ocean" emoji and "gn" with a "moon" and "ocean" emoji in the #gm-gn channel.

## Installation

* Create a new application at https://discord.com/developers/applications
* Change the general information as desired
* Go to the "Bot" section and create a bot
  * Enable "Server Members Intent"
* Create a new role for the Master of Ceremonies
* Copy `bot.ini.example` to `bot.ini` and adjust settings in `bot.ini`
  * Get the bot token in the "Bot" section and set it
  * Set channel ID
  * Set role ID
  * Set custom emojis
* Install Python and `pipenv`
* Run `pipenv install`
* Run `pipenv run python3 bot.py`
* Use the displayed URL to add the bot to the desired server
* Make sure that the bot role is higher in the hierarchy than the Master of Ceremonies
