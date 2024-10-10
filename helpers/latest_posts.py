import requests
from bs4 import BeautifulSoup

def get_latest_posts(user_profile_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(user_profile_url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []

        # Find all <a> elements with slot="full-post-link"
        post_links = soup.find_all('a', slot='full-post-link')
        
        base_url = "https://www.reddit.com"
        
        for link in post_links:
            # Extract the title from the nested <faceplate-screen-reader-content> element
            title_tag = link.find('faceplate-screen-reader-content')
            if title_tag and title_tag.text:
                post_title = title_tag.text
                post_url = base_url + link.get('href')
                posts.append({"title": post_title, "url": post_url})
                break  # Only take the first post

        return posts
    else:
        return f"Failed to retrieve the content. Status code: {response.status_code}"
