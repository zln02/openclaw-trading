#!/usr/bin/env python3
"""
24시간 자율 학습 스케줄러.
1시간마다 autonomous_research() 실행.
"""
import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.autonomous_research import autonomous_research

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def job() -> None:
    try:
        out = autonomous_research()
        logger.info("autonomous_research: %s", out)
    except Exception as e:
        logger.exception("autonomous_research failed: %s", e)


def main() -> None:
    # 즉시 1회 실행 후 1시간마다
    job()
    scheduler = BlockingScheduler()
    scheduler.add_job(job, IntervalTrigger(hours=1), id="autonomous_research")
    logger.info("자율 학습 스케줄러 시작 (1시간 간격). 종료: Ctrl+C")
    scheduler.start()


if __name__ == "__main__":
    main()
