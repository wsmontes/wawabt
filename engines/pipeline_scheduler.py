#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2025 Wagner Montes
#
# PipelineScheduler: Orquestrador master com APScheduler
# - NewsCollectorPipeline: Cada 15min
# - SentimentAnalysisPipeline: Cada 10min
# - RealtimeAlertManager: 5min (mercado) / 30min (fora)
# - SignalExecutionManager: Cada 2min
# - PerformanceTracker: Cada 15min
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import signal
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# APScheduler imports
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    logger.warning("APScheduler not installed. Install with: pip install apscheduler")
    APSCHEDULER_AVAILABLE = False

# Import pipeline components
try:
    from engines.news_collector_pipeline import NewsCollectorPipeline
    from engines.sentiment_pipeline import SentimentAnalysisPipeline
    from engines.realtime_alert_manager import RealtimeAlertManager
    from engines.signal_execution import SignalExecutionManager
    from engines.performance_tracker import PerformanceTracker
    PIPELINES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Pipeline imports failed: {e}")
    PIPELINES_AVAILABLE = False

try:
    from engines.mock_pipelines import (
        MockNewsCollectorPipeline,
        MockSentimentAnalysisPipeline,
        MockRealtimeAlertManager,
        MockSignalExecutionManager,
        MockPerformanceTracker,
    )
    MOCK_PIPELINES_AVAILABLE = True
except ImportError:
    MOCK_PIPELINES_AVAILABLE = False


class PipelineScheduler:
    """
    Master scheduler para execução automática de pipelines.
    
    Usa APScheduler para rodar pipelines em intervalos configuráveis:
    - NewsCollectorPipeline: Cada 15 minutos
    - SentimentAnalysisPipeline: Cada 10 minutos
    - RealtimeAlertManager: 5min (mercado) / 30min (fora de horário)
    - SignalExecutionManager: Cada 2 minutos
    - PerformanceTracker: Cada 15 minutos
    
    Horário de mercado US: 09:30-16:00 EST (14:30-21:00 UTC)
    """
    
    def __init__(self, 
                 enable_news_collector: bool = True,
                 enable_sentiment_analysis: bool = True,
                 enable_alert_manager: bool = True,
                 enable_signal_execution: bool = True,
                 enable_performance_tracker: bool = True,
                 test_mode: bool = False,
                 use_mock_pipelines: bool = False,
                 fixtures_dir: str = 'tests/fixtures/pipeline'):
        """
        Initialize PipelineScheduler.
        
        Args:
            enable_news_collector: Enable NewsCollectorPipeline
            enable_sentiment_analysis: Enable SentimentAnalysisPipeline
            enable_alert_manager: Enable RealtimeAlertManager
            enable_signal_execution: Enable SignalExecutionManager
            enable_performance_tracker: Enable PerformanceTracker
            test_mode: Run all jobs once immediately for testing
        """
        if not APSCHEDULER_AVAILABLE:
            raise RuntimeError("APScheduler not installed")

        self.use_mock_pipelines = use_mock_pipelines
        self.fixtures_dir = Path(fixtures_dir)

        if self.use_mock_pipelines:
            if not MOCK_PIPELINES_AVAILABLE:
                raise RuntimeError("Mock pipelines module not available")
            logger.info("Using mock pipeline implementations (fixtures: %s)", self.fixtures_dir)
        else:
            if not PIPELINES_AVAILABLE:
                raise RuntimeError("Pipeline imports failed")
        
        self.test_mode = test_mode
        
        # Pipeline enable flags
        self.enable_news_collector = enable_news_collector
        self.enable_sentiment_analysis = enable_sentiment_analysis
        self.enable_alert_manager = enable_alert_manager
        self.enable_signal_execution = enable_signal_execution
        self.enable_performance_tracker = enable_performance_tracker
        
        # Initialize scheduler
        self.scheduler = BackgroundScheduler()
        
        # Initialize pipeline instances (lazy - created on first run)
        self.news_collector = None
        self.sentiment_pipeline = None
        self.alert_manager = None
        self.signal_executor = None
        self.performance_tracker = None
        
        logger.info("PipelineScheduler initialized")
    
    def start(self):
        """Start the scheduler and register jobs"""
        logger.info("=" * 80)
        logger.info("STARTING PIPELINE SCHEDULER")
        logger.info("=" * 80)
        
        # Register jobs
        if self.enable_news_collector:
            self._register_news_collector()
        
        if self.enable_sentiment_analysis:
            self._register_sentiment_pipeline()
        
        if self.enable_alert_manager:
            self._register_alert_manager()
        
        if self.enable_signal_execution:
            self._register_signal_executor()
        
        if self.enable_performance_tracker:
            self._register_performance_tracker()
        
        # Start scheduler
        self.scheduler.start()
        logger.info("Scheduler started successfully")
        
        # Print schedule
        self._print_schedule()
        
        # Test mode: run all jobs once
        if self.test_mode:
            logger.info("TEST MODE: Running all jobs once...")
            self._run_test_cycle()
    
    def _register_news_collector(self):
        """Register NewsCollectorPipeline job - Every 15 minutes"""
        self.scheduler.add_job(
            func=self._run_news_collector,
            trigger=IntervalTrigger(minutes=15),
            id='news_collector',
            name='News Collector Pipeline',
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )
        logger.info("✓ Registered: NewsCollectorPipeline (every 15min)")
    
    def _register_sentiment_pipeline(self):
        """Register SentimentAnalysisPipeline job - Every 10 minutes"""
        self.scheduler.add_job(
            func=self._run_sentiment_pipeline,
            trigger=IntervalTrigger(minutes=10),
            id='sentiment_pipeline',
            name='Sentiment Analysis Pipeline',
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )
        logger.info("✓ Registered: SentimentAnalysisPipeline (every 10min)")
    
    def _register_alert_manager(self):
        """Register RealtimeAlertManager - 5min (market) / 30min (off-market)"""
        # Market hours: 09:30-16:00 EST (14:30-21:00 UTC) Mon-Fri
        # Run every 5 minutes during market hours
        self.scheduler.add_job(
            func=self._run_alert_manager,
            trigger=CronTrigger(
                day_of_week='mon-fri',
                hour='14-20',  # 14:30-20:59 UTC
                minute='*/5'
            ),
            id='alert_manager_market',
            name='Alert Manager (Market Hours)',
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )
        
        # Run every 30 minutes off-market
        self.scheduler.add_job(
            func=self._run_alert_manager,
            trigger=IntervalTrigger(minutes=30),
            id='alert_manager_offmarket',
            name='Alert Manager (Off-Market)',
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )
        
        logger.info("✓ Registered: RealtimeAlertManager (5min market / 30min off-market)")
    
    def _register_signal_executor(self):
        """Register SignalExecutionManager - Every 2 minutes"""
        self.scheduler.add_job(
            func=self._run_signal_executor,
            trigger=IntervalTrigger(minutes=2),
            id='signal_executor',
            name='Signal Execution Manager',
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )
        logger.info("✓ Registered: SignalExecutionManager (every 2min)")
    
    def _register_performance_tracker(self):
        """Register PerformanceTracker - Every 15 minutes"""
        self.scheduler.add_job(
            func=self._run_performance_tracker,
            trigger=IntervalTrigger(minutes=15),
            id='performance_tracker',
            name='Performance Tracker',
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )
        logger.info("✓ Registered: PerformanceTracker (every 15min)")
    
    def _run_news_collector(self):
        """Execute NewsCollectorPipeline"""
        try:
            logger.info(">>> NewsCollectorPipeline START")
            
            news_collector = self._get_news_collector()
            news_collector.run(lookback_hours=24)
            
            logger.info(">>> NewsCollectorPipeline COMPLETE")
            
        except Exception as e:
            logger.error(f"NewsCollectorPipeline error: {e}", exc_info=True)
    
    def _run_sentiment_pipeline(self):
        """Execute SentimentAnalysisPipeline"""
        try:
            logger.info(">>> SentimentAnalysisPipeline START")
            
            sentiment_pipeline = self._get_sentiment_pipeline()
            if self.use_mock_pipelines:
                sentiment_pipeline.run()
            else:
                sentiment_pipeline.run(limit=100)  # Process max 100 articles per run
            
            logger.info(">>> SentimentAnalysisPipeline COMPLETE")
            
        except Exception as e:
            logger.error(f"SentimentAnalysisPipeline error: {e}", exc_info=True)
    
    def _run_alert_manager(self):
        """Execute RealtimeAlertManager"""
        try:
            logger.info(">>> RealtimeAlertManager START")
            
            alert_manager = self._get_alert_manager()
            alert_manager.run()
            
            logger.info(">>> RealtimeAlertManager COMPLETE")
            
        except Exception as e:
            logger.error(f"RealtimeAlertManager error: {e}", exc_info=True)
    
    def _run_signal_executor(self):
        """Execute SignalExecutionManager"""
        try:
            logger.info(">>> SignalExecutionManager START")
            
            signal_executor = self._get_signal_executor()
            signal_executor.run()
            
            logger.info(">>> SignalExecutionManager COMPLETE")
            
        except Exception as e:
            logger.error(f"SignalExecutionManager error: {e}", exc_info=True)
    
    def _run_performance_tracker(self):
        """Execute PerformanceTracker"""
        try:
            logger.info(">>> PerformanceTracker START")
            
            performance_tracker = self._get_performance_tracker()
            performance_tracker.run()
            
            logger.info(">>> PerformanceTracker COMPLETE")
            
        except Exception as e:
            logger.error(f"PerformanceTracker error: {e}", exc_info=True)
    
    def _run_test_cycle(self):
        """Run all enabled pipelines once for testing"""
        if self.enable_news_collector:
            self._run_news_collector()
        
        if self.enable_sentiment_analysis:
            self._run_sentiment_pipeline()
        
        if self.enable_alert_manager:
            self._run_alert_manager()
        
        if self.enable_signal_execution:
            self._run_signal_executor()
        
        if self.enable_performance_tracker:
            self._run_performance_tracker()
        
        logger.info("Test cycle complete")
    
    def _print_schedule(self):
        """Print scheduled jobs"""
        logger.info("=" * 80)
        logger.info("SCHEDULED JOBS:")
        logger.info("=" * 80)
        
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info(f"  {job.name}")
            logger.info(f"    ID: {job.id}")
            logger.info(f"    Next run: {job.next_run_time}")
            logger.info("")

    def _get_news_collector(self):
        if self.news_collector is None:
            if self.use_mock_pipelines:
                self.news_collector = MockNewsCollectorPipeline(self.fixtures_dir)
            else:
                self.news_collector = NewsCollectorPipeline()
        return self.news_collector

    def _get_sentiment_pipeline(self):
        if self.sentiment_pipeline is None:
            if self.use_mock_pipelines:
                self.sentiment_pipeline = MockSentimentAnalysisPipeline(self.fixtures_dir)
            else:
                self.sentiment_pipeline = SentimentAnalysisPipeline(device='cpu')
        return self.sentiment_pipeline

    def _get_alert_manager(self):
        if self.alert_manager is None:
            if self.use_mock_pipelines:
                self.alert_manager = MockRealtimeAlertManager(self.fixtures_dir)
            else:
                self.alert_manager = RealtimeAlertManager()
        return self.alert_manager

    def _get_signal_executor(self):
        if self.signal_executor is None:
            if self.use_mock_pipelines:
                self.signal_executor = MockSignalExecutionManager(self.fixtures_dir)
            else:
                self.signal_executor = SignalExecutionManager()
        return self.signal_executor

    def _get_performance_tracker(self):
        if self.performance_tracker is None:
            if self.use_mock_pipelines:
                self.performance_tracker = MockPerformanceTracker(self.fixtures_dir)
            else:
                self.performance_tracker = PerformanceTracker()
        return self.performance_tracker
    
    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    def wait(self):
        """Wait indefinitely (keeps main thread alive)"""
        try:
            # Keep the main thread alive
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            logger.info("=" * 80)
            logger.info("Scheduler running. Press Ctrl+C to stop.")
            logger.info("=" * 80)
            
            # Block forever (scheduler runs in background)
            signal.pause()
            
        except (KeyboardInterrupt, SystemExit):
            logger.info("Received shutdown signal")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Signal {signum} received, shutting down...")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pipeline Scheduler')
    
    parser.add_argument('--test', action='store_true',
                       help='Test mode: run all pipelines once and exit')
    
    parser.add_argument('--disable-news', action='store_true',
                       help='Disable NewsCollectorPipeline')
    
    parser.add_argument('--disable-sentiment', action='store_true',
                       help='Disable SentimentAnalysisPipeline')
    
    parser.add_argument('--disable-alerts', action='store_true',
                       help='Disable RealtimeAlertManager')
    
    parser.add_argument('--disable-execution', action='store_true',
                       help='Disable SignalExecutionManager')
    
    parser.add_argument('--disable-performance', action='store_true',
                       help='Disable PerformanceTracker')

    parser.add_argument('--mock-pipelines', action='store_true',
                        help='Use mock pipeline implementations backed by fixtures')

    parser.add_argument('--fixtures-dir', default='tests/fixtures/pipeline',
                        help='Directory containing parquet/duckdb fixtures for mock mode')
    
    args = parser.parse_args()
    
    # Create scheduler
    scheduler = PipelineScheduler(
        enable_news_collector=not args.disable_news,
        enable_sentiment_analysis=not args.disable_sentiment,
        enable_alert_manager=not args.disable_alerts,
        enable_signal_execution=not args.disable_execution,
        enable_performance_tracker=not args.disable_performance,
        test_mode=args.test,
        use_mock_pipelines=args.mock_pipelines,
        fixtures_dir=args.fixtures_dir
    )
    
    # Start scheduler
    scheduler.start()
    
    # Test mode: exit after running once
    if args.test:
        logger.info("Test complete, exiting...")
        scheduler.stop()
        return
    
    # Production mode: wait indefinitely
    scheduler.wait()


if __name__ == '__main__':
    main()
