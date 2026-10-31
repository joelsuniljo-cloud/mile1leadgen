from . import hackernews, reddit, serp

COLLECTORS = {
    "hackernews": hackernews.fetch,
    "reddit": reddit.fetch,
    "linkedin": serp.fetch_linkedin,
    "web": serp.fetch_web,
}
