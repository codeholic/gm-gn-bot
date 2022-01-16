# GM/GN Bot

Discord bot that reacts to "gm" with a "sun" and "ocean" emoji and "gn" with a "moon" and "ocean" emoji in the #gm-gn channel.

## Installation

* Create a new application at https://discord.com/developers/applications
* Change the general information as desired
* Go to the "Bot" section and create a bot
* Copy `bot.ini.example` to `bot.ini` and adjust settings
  * Click to reveal the token in the "Bot" section and set it in `bot.ini`
  * Copy channel ID and set it in `bot.ini`
  * Copy custom emoji IDs and set them in `bot.ini`
* Go to the "OAuth2 > URL Generator" section
* Choose "bot"
* Choose "Add Reactions"
* Copy and open the URL
* Add it to the desired server
* Install Python and `pipenv`
* Run `pipenv install`
* Run `pipenv shell` and then `python3 bot.py`
