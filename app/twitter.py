import json
import logging
import os
from typing import Dict, List, Tuple

import tweepy
from dotenv import find_dotenv, load_dotenv
from requests_oauthlib import OAuth1Session

load_dotenv(find_dotenv())


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

quick_reply_option = [
    {
        'label': 'Yes',
        'description': 'Yes I can provide more information',
        'metadata': 'confirm_yes'
    },
    {
        'label': 'No',
        'description': 'No I can\'t provide more information',
        'metadata': 'confirm_no'
    }
]

# Tweepy setup


def create_api():
    """ Creates tweepy api """
    consumer_key = os.getenv("CONSUMER_KEY")
    consumer_secret = os.getenv("CONSUMER_SECRET")
    access_key = os.getenv("ACCESS_KEY")
    access_secret = os.getenv("ACCESS_SECRET")
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_key, access_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True,
                     wait_on_rate_limit_notify=True)

    try:
        api.verify_credentials()
    except Exception as e:
        logger.error("Error creating API", exc_info=True)
    logger.info("API created")
    return api


def manual_twitter_api():
    manual_twitter_auth = OAuth1Session(os.getenv("CONSUMER_KEY"),
                                        os.getenv("CONSUMER_SECRET"),
                                        os.getenv("ACCESS_KEY"),
                                        os.getenv("ACCESS_SECRET"))
    logger.info("Manual API created")
    return manual_twitter_auth


# Users

def user_tweets(user_id: str) -> List[Dict]:
    """ FOR TESTING, get one user's tweets for tweet_ids to test response """
    api = create_api()
    temp = api.user_timeline(screen_name=('{}').format(user_id),
                             count=200,
                             include_rts=False,
                             tweet_mode='extended')
    tweets = []
    for tweet in temp:
        tweets.append({
            "tweet_id": tweet.id,
            "full_text": tweet.full_text,
            "author": tweet.author.screen_name
        })
    return tweets


def get_user_id_from_tweet(tweet_id):
    api = create_api()
    tweet = api.get_status(tweet_id)
    user_id = tweet.user.id
    return user_id


def get_user_id(screen_name: str) -> List[Dict]:
    """ Get user id from screenname """
    name_id_pairs = []
    api = create_api()
    resp = api.lookup_users(screen_name=screen_name)
    for user in resp:
        name_id_pairs.append({
            "screen_name": user.screen_name,
            "user_id": user.id
        })
    return name_id_pairs


# Tweets

def get_replies(user_id: str, tweet_id: int, replier_id: str) -> str:
    """ Gets replies to a tweet (tweet_id) originally posted by a user (user_id) replies from replier """
    api = create_api()
    replies = tweepy.Cursor(api.search, q='to:{}'.format(user_id),
                            since_id=tweet_id, tweet_mode='extended').items(100)
    list_replies = []

    while True:
        try:
            reply = replies.next()
            if not hasattr(reply, 'in_reply_to_status_id_str'):
                continue
            if reply.in_reply_to_status_id == int(tweet_id) and reply.user.screen_name == replier_id:
                return reply
        except tweepy.RateLimitError as e:
            logging.error("Twitter api rate limit reached".format(e))
            break
        except tweepy.TweepError as e:
            logging.error("Tweepy error occured:{}".format(e))
            break
        except StopIteration:
            print('StopIteration')
            break
        except Exception as e:
            logger.error("Failed while fetching replies {}".format(e))
            break


def respond_to_tweet(tweet_id: int, tweet_body: str) -> str:
    """ Function to reply to a certain tweet_id """
    api = create_api()
    return api.update_status(status=tweet_body, in_reply_to_status_id=tweet_id, autopopulate_reply_metadata=True)


# Direct messaging


def create_welcome_message(name: str,
                           msg_txt: str,
                           quick_replies: List[Dict] = None):  # Use quick_reply_option
    manual_twitter_auth = manual_twitter_api()
    url = "https://api.twitter.com/1.1/direct_messages/welcome_messages/new.json"
    if quick_replies:
        payload = json.dumps({
            "welcome_message": {
                "name": name,
                "message_data": {
                    "text": msg_txt,
                    "quick_reply": {
                        "type": "options",
                                "options": quick_replies
                    }
                }
            }
        })
    else:
        payload = json.dumps({
            "welcome_message": {
                "name": name,
                "message_data": {
                    "text": msg_txt
                }
            }
        })
    headers = {
        'Content-Type': 'application/json'
    }

    response = manual_twitter_auth.post(url, headers=headers, data=payload)

    welcome_response = json.loads(response.text)
    print(welcome_response)


def send_dm(user_id: str, dm_body: str) -> str:
    """ Function to send dm to a given user_id """
    api = create_api()
    dm = api.send_direct_message(user_id, dm_body)
    return dm


def process_dms(user_id: str, tweet_id: str, convo_tree_txt: str) -> Dict:
    """Function to get response DMs sent from button in tweet"""
    api = create_api()
    dms = api.list_direct_messages()
    screen_name = str(get_user_id(user_id)[0]['user_id'])

    dm_list = []
    for dm in dms:

        if dm.message_create['sender_id'] == screen_name:
            data = {}

            if dm.message_create['message_data']['quick_reply_response']['metadata'] == 'confirm_yes':

                form_link = f'https://a.humanrightsfirst.dev/edit/{tweet_id}'
                response_txt = convo_tree_txt + '\n' + form_link

                api.send_direct_message(screen_name, response_txt)
                data['conversation_status'] = 11
            else:
                api.send_direct_message(screen_name, convo_tree_txt)
                data['conversation_status'] = 13

            data['tweet_id'] = tweet_id
            data["reachout_template"] = dm.initiated_via['welcome_message_id'],
            data["tweeter_id"] = dm.message_create['sender_id'],
            data["dm_text"] = dm.message_create['message_data']['text'],
            data["quick_reply_response"] = dm.message_create['message_data']['quick_reply_response']['metadata']

            return data
