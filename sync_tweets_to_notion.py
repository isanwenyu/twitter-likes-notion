import os
import re
import tweepy
import openai
from notion_client import Client

# 获取Twitter API密钥
consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

# 获取OpenAI API密钥
openai.api_key = os.environ.get("OPENAI_API_KEY")

# 获取Notion API密钥和数据库ID
notion = Client(auth=os.environ.get("NOTION_API_KEY"))
database_id = os.environ.get("DATABASE_ID")

# 获取同步方式
sync_mode = os.environ.get("SYNC_MODE")

# 获取Twitter用户喜欢的推文列表
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)
if sync_mode == "full":
    tweets = api.favorites(count=1000)
else:
    latest_tweet_id = notion.databases.query(
        **{
            "database_id": database_id,
            "sorts": [{"property": "Created Time", "direction": "descending"}],
            "page_size": 1
        }
    ).get("results")[0].get("properties").get("URL").get("url").split("/")[-1]
    tweets = api.favorites(count=10, since_id=latest_tweet_id)

# 遍历推文列表，并将推文数据同步到Notion中
for tweet in tweets:
    # 获取推文标题和链接
    title = tweet.text
    url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}"

    # 使用OpenAI生成推文总结和标签
    response = openai.Completion.create(
      engine="text-davinci-002",
      prompt=f"Summarize this tweet: {title}\n\nGenerate tags for this tweet:",
      max_tokens=60,
      n=1,
      stop=None,
      temperature=0.5,
    )
    summary = response.choices[0].text.strip()
    tags = [tag.strip() for tag in response.choices[0].text.split(",")]

    # 将标签转换为Notion数据库中的格式
    tag_list = []
    for tag in tags:
        tag_list.append({"name": tag})

    # 检查推文是否已经在Notion数据库中存在
    existing_records = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "property": "URL",
                "url": {"equals": url}
            }
        }
    ).get("results")

    # 如果推文不存在，则创建一条新记录
    if not existing_records:
        new_record = {
            "Title": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url},
            "Summary": {"rich_text": [{"text": {"content": summary}}]},
            "Tags": {"multi_select": tag_list}
        }
        notion.pages.create(parent={"database_id": database_id}, properties=new_record)
    # 如果推文已经存在，则更新记录的内容
    else:
        record_id = existing_records[0]["id"]
        updated_record = {
            "Title": {"title": [{"text": {"content": title}}]},
            "Summary": {"rich_text": [{"text": {"content": summary}}]},
            "Tags": {"multi_select": tag_list}
        }
        notion.pages.update(page_id=record_id, properties=updated_record)