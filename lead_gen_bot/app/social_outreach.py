import logging
import asyncio
import praw
import tweepy
from linkedin_api import Linkedin

logger = logging.getLogger(__name__)

class ZoraSocialEngine:
    def __init__(self, credentials: dict):
        """
        credentials format:
        {
            "reddit": {"client_id": "", "client_secret": "", "username": "", "password": "", "user_agent": "ZoraBot/1.0"},
            "twitter": {"api_key": "", "api_secret": "", "access_token": "", "access_token_secret": ""},
            "linkedin": {"username": "", "password": ""}
        }
        """
        self.creds = credentials

        # Initialize Reddit
        self.reddit = None
        if self.creds.get("reddit") and self.creds["reddit"].get("client_id"):
            try:
                rc = self.creds["reddit"]
                self.reddit = praw.Reddit(
                    client_id=rc["client_id"],
                    client_secret=rc["client_secret"],
                    username=rc["username"],
                    password=rc["password"],
                    user_agent=rc.get("user_agent", "ZoraBot/1.0")
                )
                logger.info("Reddit engine initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Reddit: {e}")

        # Initialize Twitter/X
        self.twitter = None
        if self.creds.get("twitter") and self.creds["twitter"].get("api_key"):
            try:
                tc = self.creds["twitter"]
                # Using Tweepy V2 client for modern X API
                self.twitter = tweepy.Client(
                    consumer_key=tc["api_key"],
                    consumer_secret=tc["api_secret"],
                    access_token=tc["access_token"],
                    access_token_secret=tc["access_token_secret"]
                )
                logger.info("Twitter engine initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Twitter: {e}")

        # Initialize LinkedIn
        self.linkedin = None
        if self.creds.get("linkedin") and self.creds["linkedin"].get("username"):
            try:
                lc = self.creds["linkedin"]
                self.linkedin = Linkedin(lc["username"], lc["password"])
                logger.info("LinkedIn engine initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize LinkedIn: {e}")

    async def post_to_reddit(self, subreddits: list, title: str, content: str) -> dict:
        """
        Posts a thread to target subreddits.
        """
        if not self.reddit:
            return {"status": "skipped", "reason": "Reddit not configured"}

        results = {"success": [], "failed": []}

        def _post():
            for sub in subreddits:
                try:
                    subreddit = self.reddit.subreddit(sub.strip().replace("r/", ""))
                    submission = subreddit.submit(title=title, selftext=content)
                    results["success"].append(f"r/{sub}: {submission.url}")
                except Exception as e:
                    logger.error(f"Reddit post failed for r/{sub}: {e}")
                    results["failed"].append(f"r/{sub}: {e}")
            return results

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _post)

    async def post_to_twitter(self, text: str) -> dict:
        """
        Posts a single tweet or thread (if text is very long, it splits it).
        """
        if not self.twitter:
            return {"status": "skipped", "reason": "Twitter not configured"}

        def _post():
            try:
                # Basic split if over 280 chars to create a thread
                if len(text) > 280:
                    chunks = [text[i:i+275] for i in range(0, len(text), 275)]
                    previous_tweet_id = None
                    urls = []
                    for i, chunk in enumerate(chunks):
                        part = f"{chunk} {i+1}/{len(chunks)}"
                        if previous_tweet_id:
                            resp = self.twitter.create_tweet(text=part, in_reply_to_tweet_id=previous_tweet_id)
                        else:
                            resp = self.twitter.create_tweet(text=part)
                        previous_tweet_id = resp.data['id']
                        urls.append(f"https://x.com/user/status/{previous_tweet_id}")
                    return {"status": "success", "urls": urls}
                else:
                    resp = self.twitter.create_tweet(text=text)
                    return {"status": "success", "url": f"https://x.com/user/status/{resp.data['id']}"}
            except Exception as e:
                logger.error(f"Twitter post failed: {e}")
                return {"status": "failed", "error": str(e)}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _post)

    async def message_linkedin_connections(self, message: str, limit: int = 50) -> dict:
        """
        Sends a direct message to current 1st-degree connections.
        """
        if not self.linkedin:
            return {"status": "skipped", "reason": "LinkedIn not configured"}

        def _post():
            results = {"success": 0, "failed": 0}
            try:
                # Fetch recent connections
                connections = self.linkedin.get_profile_connections(self.linkedin.client.get_user_profile()['urn_id'])
                count = 0
                for conn in connections:
                    if count >= limit: break
                    try:
                        urn_id = conn['entityUrn'].split(':')[-1]
                        self.linkedin.send_message(message, [urn_id])
                        results["success"] += 1
                        count += 1
                    except Exception as e:
                        results["failed"] += 1
                return results
            except Exception as e:
                logger.error(f"LinkedIn messaging failed: {e}")
                return {"status": "failed", "error": str(e)}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _post)
