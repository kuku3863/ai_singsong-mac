# -*- coding: utf-8 -*-
from locust import HttpUser, task, between, events
import json
import random
import time
import os
import requests

HOST = "https://klrvc.com"
DURATION = 6 * 60 * 60
CLEAR_CACHE_BEFORE = True

json_path = os.path.join(os.path.dirname(__file__), "klrvc_resources.json")
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        all_resources = json.load(f)
else:
    all_resources = []

images = [r["url"] for r in all_resources if r.get("type") == "img" and r["url"].startswith("http")]
pages = [r["url"] for r in all_resources if r.get("type") == "xmlhttprequest" and "/page/" in r["url"]]
statics = [r["url"] for r in all_resources if r.get("type") in ["link", "script", "css"] and r["url"].startswith("http")]

print(f"[压力测试] 加载资源完成 → 图片: {len(images)} | 分页: {len(pages)} | 静态资源: {len(statics)}")

def clear_all_cache():
    print("[压力测试] 正在清除缓存...")
    purge_endpoints = [
        "https://klrvc.com/purge",
        "https://klrvc.com/cache/clear",
        "https://klrvc.com/api/cache/clear",
        "https://klrvc.com/?clear_cache=1",
    ]
    for endpoint in purge_endpoints:
        try:
            requests.get(endpoint, timeout=5, verify=False)
        except:
            pass
    print("[压力测试] 缓存清除完成，开始压测...")

if CLEAR_CACHE_BEFORE:
    clear_all_cache()

class KlrvcUser(HttpUser):
    host = HOST
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.client.get("/", name="首页")

    @task(5)
    def browse_pages(self):
        if pages:
            page_url = random.choice(pages)
            self.client.get(page_url, name="分页加载")

    @task(10)
    def load_images(self):
        if images:
            num = random.randint(8, 15)
            selected = random.sample(images, min(num, len(images)))
            for img_url in selected:
                self.client.get(img_url, name="模型图片")

    @task(3)
    def load_statics(self):
        if statics:
            static_url = random.choice(statics)
            self.client.get(static_url, name="静态资源")

    @task(2)
    def view_random_model(self):
        model_urls = ["/mxgf/3241.html", "/mxgf/3179.html", "/mxgf/4005.html"]
        url = random.choice(model_urls)
        self.client.get(url, name="模型详情页")

    @task(20)
    def cycle_load_and_clear_cache(self):
        if pages:
            for page_url in random.sample(pages, min(3, len(pages))):
                self.client.get(page_url, name="循环-分页")

        if images:
            num = random.randint(15, 25)
            selected = random.sample(images, min(num, len(images)))
            for img_url in selected:
                self.client.get(img_url, name="循环-图片")

        if statics:
            for _ in range(5):
                static_url = random.choice(statics)
                self.client.get(static_url, name="循环-静态")

        purge_endpoints = [
            "https://klrvc.com/purge",
            "https://klrvc.com/cache/clear",
            "https://klrvc.com/api/cache/clear",
        ]
        for endpoint in purge_endpoints:
            try:
                self.client.get(endpoint, name="缓存清除", catch_response=True)
            except:
                pass

        for _ in range(15):
            random_path = f"/mxgf/{random.randint(1000, 5000)}.html"
            self.client.get(random_path, name="缓存压力测试")

        time.sleep(0.1)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"[压力测试] 开始运行，持续 {DURATION//3600} 小时...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("[压力测试] 测试结束")
