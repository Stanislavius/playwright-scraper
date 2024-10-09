import asyncio
import random

from fake_headers import Headers
from playwright.async_api import async_playwright, Playwright
import os

browser_endpoint = os.getenv("browser_endpoint")
storage_state = os.getenv("storage_state")

login_url = "https://twitter.com/i/flow/login"
x_login = os.getenv("x_login")
x_password = os.getenv("x_password")
x_username = os.getenv("x_username")
screen_num = 1


async def prepare_page(page):
    await page.add_init_script('''Object.defineProperty(navigator, "languages", {
                          get: function() {
                            return ["en-GB", "en"]
                          }
                        });
                        ''')

    await page.add_init_script('''Object.defineProperty(navigator, "doNotTrack", {
                      get: function() {
                        return 1;
                      }
                    });
                    ''')
    await page.add_init_script('''Object.defineProperty(navigator, "deviceMemory", {
                      get: function() {
                        return 4;
                      }
                    });
                    ''')
    return page


async def get_browser_and_context(p: Playwright):
    header = Headers(browser="chrome", os="windows", headers=True).generate()['User-Agent']
    browser = await p.chromium.connect(browser_endpoint)
    context = await browser.new_context(timezone_id="Europe/Kiev",
                                        user_agent=header,
                                        viewport={"width": 1920, "height": 1080},
                                        storage_state=storage_state)
    page = await context.new_page()
    page = await prepare_page(page)
    return browser, context, page


async def click_following(page):
    await page.wait_for_selector(':has-text("Following")', timeout=20000)
    await page.get_by_text("Following").click()


async def process_one_tweet(page, tweet):
    show_more = await tweet.query_selector('[data-testid="tweet-text-show-more-link"]')
    if show_more:
        print("Show more найден")
        await asyncio.sleep(random.randint(100, 400)/1000)
        await show_more.click()
        await page.wait_for_selector('//article[@data-testid="tweet" and not(@disabled)]', timeout=10000)
        tweets = await page.query_selector_all('//article[@data-testid="tweet" and not(@disabled)]')
        tweet = tweets[0] if tweets else None
    else:
        print("Show more не найден")

    global screen_num
    screen_name = f"{screen_num}.png"
    screen_num += 1
    await tweet.screenshot(path=screen_name)

    element_user = await tweet.query_selector('div[data-testid="User-Name"]') if tweet else None
    text_user = await page.evaluate('(element) => element.textContent', element_user) if element_user else None

    element_datetime = await tweet.query_selector('time[datetime]') if tweet else None
    datetime_value = await page.evaluate('(element) => element.getAttribute("datetime")',
                                         element_datetime) if element_datetime else None
    text_element = await tweet.query_selector('div[data-testid="tweetText"]') if tweet else None
    tweet_text = await page.evaluate('(element) => element.textContent', text_element) if text_element else None

    tweet_links = await tweet.query_selector_all('a[role=link][href*=status]') if tweet else []
    tweet_link = await page.evaluate('(element) => element.getAttribute("href")',
                                     tweet_links[0]) if tweet_links else None
    tweet_link = f"x.com{tweet_link}" if tweet_link else None

    if show_more:
        await page.go_back()

    return datetime_value, tweet_text, tweet_link, text_user, screen_name


async def scrap():
    async with async_playwright() as p:
        browser, context, page = await get_browser_and_context(p)

        await page.goto(login_url)

        await page.fill('input[autocomplete="username"]', x_login)
        await page.press('input[autocomplete="username"]', 'Enter')

        try:
            await page.wait_for_selector('input[data-testid="ocfEnterTextTextInput"]', timeout=3000)
            await page.fill('input[data-testid="ocfEnterTextTextInput"]', x_username)
            await page.press('input[data-testid="ocfEnterTextTextInput"]', 'Enter')
        except Exception as e:
            pass

        await page.wait_for_selector('input[name="password"]', timeout=10000)
        await page.fill('input[name="password"]', x_password)
        await page.press('input[name="password"]', 'Enter')

        try:
            await page.wait_for_selector('input[data-testid="ocfEnterTextTextInput"]', timeout=10000)
            print("Confirmation code is required")
            code = input("Confirmation_code: ")
            await page.fill('input[data-testid="ocfEnterTextTextInput"]', code)
            await page.press('input[data-testid="ocfEnterTextTextInput"]', 'Enter')
        except Exception as e:
            print("No confirmation code is required.")

        await context.storage_state(path=storage_state)
        print("Session saved.")

        await page.goto("https://x.com/home")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

        try:
            await click_following(page)
        except Exception as e:
            print("Click following error")

        result = []
        tweet_count = 0
        max_tweet_count = 100
        tries = 0
        while tweet_count < max_tweet_count:
            tweets = await page.query_selector_all('//article[@data-testid="tweet" and not(@disabled)]')
            try:
                tweet = tweets[tweet_count]
            except Exception as e:
                await page.evaluate(f"window.scrollTo(0, window.scrollY + {random.randint(630, 1200)});")
                tries += 1
                if tries == 10:
                    await browser.close()
                    return result
                continue

            bb = await tweet.bounding_box()
            height = bb.get("height")
            new_tweet = await process_one_tweet(page, tweet)
            result.append(new_tweet)
            await page.evaluate(f"window.scrollTo(0, window.scrollY + {height});")

            tweet_count += 1

        await browser.close()

