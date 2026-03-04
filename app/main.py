from fastapi import FastAPI, HTTPException, Query
from playwright.sync_api import sync_playwright
import time
import random
import re

app = FastAPI(title="Naukri Scraper API")

# ── Known multi-word / special skills ──────────────────────
KNOWN_SKILLS = sorted([
    "node.js", "react.js", "vue.js", "next.js", "express.js", "angular.js",
    "mern stack", "mean stack", "lamp stack", "full stack", "fullstack",
    "ruby on rails", "machine learning", "deep learning", "natural language processing",
    "artificial intelligence", "computer vision", "data science", "data engineering",
    "sql server", "sql development", "stored procedures", "database design",
    "performance tuning", "rest api", "restful api", "web services", "micro services",
    "microservices", "spring boot", "asp.net", ".net core", "entity framework",
    "ci/cd", "docker", "kubernetes", "git", "github", "gitlab",
    "aws", "gcp", "azure", "google cloud",
    "mongodb", "postgresql", "mysql", "sqlite", "oracle", "cassandra", "redis",
    "django", "flask", "laravel", "codeigniter", "fastapi",
    "html", "css", "scss", "sass", "tailwind", "bootstrap",
    "javascript", "typescript", "jquery", "ajax",
    "java", "python", "ruby", "php", "golang", "kotlin", "swift", "scala",
    "linux", "unix", "bash", "shell scripting",
    "dbms", "nosql", "graphql", "json", "xml", "yaml",
    "plsql", "pl/sql", "hadoop", "spark", "kafka",
    "react native", "flutter", "android", "ios",
    "nginx", "apache", "jenkins", "ansible", "terraform",
    "object oriented", "data structures", "design patterns", "agile", "scrum",
], key=len, reverse=True)

# ---------------------------------------
# Helpers
# ---------------------------------------

def human_delay(a=2, b=4):
    time.sleep(random.uniform(a, b))

def build_url(skill: str, location: str, experience: int):
    skill_slug = skill.strip().lower().replace(" ", "-")
    location_slug = location.strip().lower().replace(" ", "-")
    skill_param = skill.strip().lower().replace(" ", "+")

    # experience=0 means fresher
    return (
        f"https://www.naukri.com/{skill_slug}-jobs-in-{location_slug}"
        f"?k={skill_param}&l={location_slug}&experience={experience}"
    )

def clean_text(text):
    return text.strip() if text else "N/A"

def clean_skills(raw: str) -> list:
    if not raw or raw == "N/A":
        return []

    text = raw.strip().lower()
    text = re.sub(r'(?i)key\s*skills?\s*[\n\r:]*', '', text)
    parts = re.split(r'[\n\r,|;/]+', text)

    found = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        for phrase in KNOWN_SKILLS:
            if phrase in part:
                if phrase not in found:
                    found.append(phrase)
                part = part.replace(phrase, " ")

        remainder = part.strip()
        if remainder:
            spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', remainder)
            spaced = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', spaced)
            spaced = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', spaced)

            tokens = spaced.split()
            for token in tokens:
                token = token.strip().strip(".")
                if len(token) > 1 and token not in found:
                    found.append(token)

    result = []
    for s in found:
        if "." in s:
            result.append(s)
        else:
            result.append(s.title())

    # remove duplicates
    seen = set()
    deduped = []
    for s in result:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    return deduped


# ---------------------------------------
# MAIN ROUTE
# ---------------------------------------

@app.get("/scrape")
def scrape(
    skill: str = Query(...),
    location: str = Query(...),
    experience: int = Query(0)  # ✅ Default = 0 (Fresher)
):

    url = build_url(skill, location, experience)
    jobs_data = []
    seen_links = set()

    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
            )

            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="en-IN",
                timezone_id="Asia/Kolkata"
            )

            page = context.new_page()
            page.goto(url, timeout=60000)
            human_delay(5, 7)

            # Scroll to load dynamic content
            for _ in range(6):
                page.mouse.wheel(0, 1200)
                human_delay(1, 2)

            selectors = [
                "article.jobTuple",
                "div.jobTuple",
                "div[class*='tuple']",
                "div[class*='job-card']"
            ]

            cards = []
            for sel in selectors:
                found = page.query_selector_all(sel)
                if found and len(found) > 0:
                    cards = found
                    break

            if not cards:
                page.screenshot(path="debug.png")
                browser.close()
                return {"success": False, "count": 0, "jobs": []}

            for card in cards:

                title_el = card.query_selector("a.title, h2 a, h3 a")
                if not title_el:
                    continue

                link = title_el.get_attribute("href")
                title = clean_text(title_el.inner_text())

                if not link or link in seen_links:
                    continue

                seen_links.add(link)

                company_el = card.query_selector(".comp-name, .company")
                exp_el = card.query_selector(".expwdth, .exp")
                loc_el = card.query_selector(".loc-wrap, .loc")
                salary_el = card.query_selector(".sal-wrap, .salary")
                posted_el = card.query_selector(".job-post-day")
                skills_el = card.query_selector(".tags-gt, .skill-stack")

                raw_skills = clean_text(skills_el.inner_text()) if skills_el else "N/A"

                jobs_data.append({
                    "Search_Skill": skill.title(),
                    "Title": title,
                    "Company": clean_text(company_el.inner_text()) if company_el else "N/A",
                    "Experience": clean_text(exp_el.inner_text()) if exp_el else "N/A",
                    "Salary": clean_text(salary_el.inner_text()) if salary_el else "N/A",
                    "Location": clean_text(loc_el.inner_text()) if loc_el else "N/A",
                    "Skills": clean_skills(raw_skills),
                    "Posted": clean_text(posted_el.inner_text()) if posted_el else "N/A",
                    "Link": link
                })

                if len(jobs_data) == 10:
                    break

            browser.close()

        return {
            "success": True,
            "experience_filter": "Fresher" if experience == 0 else f"{experience}+ years",
            "count": len(jobs_data),
            "jobs": jobs_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))