#!/usr/bin/env python3
"""
HomeWizard P1 Exporter - Main Application

This application polls data from a HomeWizard P1 meter (HWE-P1-G1),
stores it in a PostgreSQL database, and generates yearly consumption reports.
"""

import os
import sys
import time
import logging
from datetime import datetime
import requests
import psycopg2
from psycopg2 import sql
import schedule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HomeWizardClient:
    """Client for interacting with HomeWizard P1 Meter API"""
    
    def __init__(self, host):
        self.host = host
        self.api_url = f"http://{host}/api/v1/data"
        
    def get_data(self):
        """Fetch current data from the HomeWizard P1 meter"""
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from HomeWizard: {e}")
            return None


class DatabaseManager:
    """Manage database connections and operations"""
    
    def __init__(self, host, port, database, user, password):
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        self.connection = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            logger.info("Database connection established")
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
            
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
            
    def init_schema(self):
        """Initialize database schema"""
        try:
            cursor = self.connection.cursor()
            
            # Create measurements table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    power_consumed REAL,
                    power_produced REAL,
                    total_imported REAL,
                    total_exported REAL,
                    gas_timestamp TIMESTAMP,
                    gas_total_m3 REAL,
                    voltage_l1 REAL,
                    voltage_l2 REAL,
                    voltage_l3 REAL,
                    current_l1 REAL,
                    current_l2 REAL,
                    current_l3 REAL,
                    UNIQUE(timestamp)
                )
            """)
            
            # Create index on timestamp for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_measurements_timestamp 
                ON measurements(timestamp)
            """)
            
            self.connection.commit()
            cursor.close()
            logger.info("Database schema initialized")
        except psycopg2.Error as e:
            logger.error(f"Error initializing schema: {e}")
            self.connection.rollback()
            raise
            
    def store_measurement(self, data):
        """Store a measurement in the database"""
        try:
            cursor = self.connection.cursor()
            
            timestamp = datetime.now()
            electricity = data.get('electricity', {})
            gas = data.get('gas', {})
            
            # Parse gas timestamp if available
            gas_timestamp = None
            if gas.get('timestamp'):
                try:
                    gas_timestamp = datetime.fromisoformat(gas['timestamp'].replace('Z', '+00:00'))
                except ValueError:
                    pass
            
            cursor.execute("""
                INSERT INTO measurements (
                    timestamp, power_consumed, power_produced,
                    total_imported, total_exported,
                    gas_timestamp, gas_total_m3,
                    voltage_l1, voltage_l2, voltage_l3,
                    current_l1, current_l2, current_l3
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp) DO NOTHING
            """, (
                timestamp,
                electricity.get('power_consumed'),
                electricity.get('power_produced'),
                electricity.get('total_imported'),
                electricity.get('total_exported'),
                gas_timestamp,
                gas.get('total_m3'),
                electricity.get('voltage_phase_l1'),
                electricity.get('voltage_phase_l2'),
                electricity.get('voltage_phase_l3'),
                electricity.get('current_phase_l1'),
                electricity.get('current_phase_l2'),
                electricity.get('current_phase_l3')
            ))
            
            self.connection.commit()
            cursor.close()
            logger.debug("Measurement stored successfully")
            return True
        except psycopg2.Error as e:
            logger.error(f"Error storing measurement: {e}")
            self.connection.rollback()
            return False
            
    def get_yearly_consumption(self, year):
        """Get yearly consumption statistics"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT 
                    MIN(total_imported) as start_imported,
                    MAX(total_imported) as end_imported,
                    MIN(total_exported) as start_exported,
                    MAX(total_exported) as end_exported,
                    MIN(gas_total_m3) as start_gas,
                    MAX(gas_total_m3) as end_gas
                FROM measurements
                WHERE EXTRACT(YEAR FROM timestamp) = %s
            """, (year,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result and result[0] is not None:
                return {
                    'year': year,
                    'electricity_consumed_kwh': round((result[1] or 0) - (result[0] or 0), 2),
                    'electricity_produced_kwh': round((result[3] or 0) - (result[2] or 0), 2),
                    'gas_consumed_m3': round((result[5] or 0) - (result[4] or 0), 2)
                }
            return None
        except psycopg2.Error as e:
            logger.error(f"Error getting yearly consumption: {e}")
            return None


class HomeWizardExporter:
    """Main application class"""
    
    def __init__(self):
        # Load configuration from environment variables
        self.hw_host = os.getenv('HOMEWIZARD_HOST')
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME', 'homewizard')
        self.db_user = os.getenv('DB_USER', 'postgres')
        self.db_password = os.getenv('DB_PASSWORD', 'postgres')
        self.poll_interval = int(os.getenv('POLL_INTERVAL', '30'))
        
        if not self.hw_host:
            logger.error("HOMEWIZARD_HOST environment variable is required")
            sys.exit(1)
            
        self.client = HomeWizardClient(self.hw_host)
        self.db = DatabaseManager(
            self.db_host,
            self.db_port,
            self.db_name,
            self.db_user,
            self.db_password
        )
        
    def poll_and_store(self):
        """Poll data from HomeWizard and store in database"""
        logger.info("Polling HomeWizard meter...")
        data = self.client.get_data()
        
        if data:
            logger.info(f"Received data: Power={data.get('electricity', {}).get('power_consumed', 0)}W, "
                       f"Gas={data.get('gas', {}).get('total_m3', 0)}m³")
            self.db.store_measurement(data)
        else:
            logger.warning("No data received from HomeWizard")
            
    def generate_report(self, year=None):
        """Generate yearly consumption report"""
        if year is None:
            year = datetime.now().year
            
        logger.info(f"Generating report for year {year}")
        stats = self.db.get_yearly_consumption(year)
        
        if stats:
            logger.info(f"\n=== Yearly Report {year} ===")
            logger.info(f"Electricity Consumed: {stats['electricity_consumed_kwh']} kWh")
            logger.info(f"Electricity Produced: {stats['electricity_produced_kwh']} kWh")
            logger.info(f"Gas Consumed: {stats['gas_consumed_m3']} m³")
            logger.info("========================\n")
            return stats
        else:
            logger.warning(f"No data available for year {year}")
            return None
            
    def run(self):
        """Run the main application loop"""
        logger.info("Starting HomeWizard Exporter")
        logger.info(f"HomeWizard Host: {self.hw_host}")
        logger.info(f"Poll Interval: {self.poll_interval} seconds")
        
        # Connect to database and initialize schema
        max_retries = 5
        for i in range(max_retries):
            try:
                self.db.connect()
                self.db.init_schema()
                break
            except Exception as e:
                if i < max_retries - 1:
                    logger.warning(f"Database connection failed, retrying in 5 seconds... ({i+1}/{max_retries})")
                    time.sleep(5)
                else:
                    logger.error("Failed to connect to database after multiple retries")
                    sys.exit(1)
        
        # Schedule data collection
        schedule.every(self.poll_interval).seconds.do(self.poll_and_store)
        
        # Schedule daily report at midnight
        schedule.every().day.at("00:00").do(self.generate_report)
        
        # Do initial poll
        self.poll_and_store()
        
        # Run scheduler
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.db.close()


if __name__ == '__main__':
    app = HomeWizardExporter()
    app.run()
