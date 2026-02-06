#!/usr/bin/env python3
"""
Generate consumption reports from stored HomeWizard data.

This script can generate yearly consumption reports and export them
to CSV or JSON format.
"""

import os
import sys
import argparse
import json
import csv
from datetime import datetime
import psycopg2


class ReportGenerator:
    """Generate consumption reports"""
    
    def __init__(self, host, port, database, user, password):
        try:
            self.connection = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
        except psycopg2.Error as e:
            raise RuntimeError(f"Failed to connect to database: {e}") from e
        
    def close(self):
        """Close database connection"""
        self.connection.close()
        
    def get_yearly_consumption(self, year):
        """Get yearly consumption statistics.
        
        This implementation is resilient to counter resets and data gaps by
        summing only positive deltas between consecutive measurements.
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT
                    timestamp,
                    total_imported,
                    total_exported,
                    gas_total_m3
                FROM measurements
                WHERE EXTRACT(YEAR FROM timestamp) = %s
                ORDER BY timestamp
            """, (year,))
            
            rows = cursor.fetchall()
            
            # No data for this year
            if not rows:
                return {}
            
            electricity_consumed = 0.0
            electricity_produced = 0.0
            gas_consumed = 0.0
            
            # Initialize with the first row's values
            _, prev_imported, prev_exported, prev_gas = rows[0]
            
            # Walk through consecutive measurements and sum positive deltas
            for row in rows[1:]:
                _, curr_imported, curr_exported, curr_gas = row
                
                if (
                    prev_imported is not None
                    and curr_imported is not None
                    and curr_imported >= prev_imported
                ):
                    electricity_consumed += float(curr_imported) - float(prev_imported)
                
                if (
                    prev_exported is not None
                    and curr_exported is not None
                    and curr_exported >= prev_exported
                ):
                    electricity_produced += float(curr_exported) - float(prev_exported)
                
                if (
                    prev_gas is not None
                    and curr_gas is not None
                    and curr_gas >= prev_gas
                ):
                    gas_consumed += float(curr_gas) - float(prev_gas)
                
                prev_imported, prev_exported, prev_gas = curr_imported, curr_exported, curr_gas
            
            return {
                'year': year,
                'electricity_consumed_kwh': round(electricity_consumed, 2),
                'electricity_produced_kwh': round(electricity_produced, 2),
                'gas_consumed_m3': round(gas_consumed, 2),
                'measurement_count': len(rows)
            }
        finally:
            if cursor:
                cursor.close()
        
    def get_monthly_consumption(self, year):
        """Get monthly consumption statistics for a year.
        
        Note: Only returns months with data. Missing months are not included.
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT 
                    EXTRACT(MONTH FROM timestamp) as month,
                    MIN(total_imported) as start_imported,
                    MAX(total_imported) as end_imported,
                    MIN(total_exported) as start_exported,
                    MAX(total_exported) as end_exported,
                    MIN(gas_total_m3) as start_gas,
                    MAX(gas_total_m3) as end_gas
                FROM measurements
                WHERE EXTRACT(YEAR FROM timestamp) = %s
                GROUP BY EXTRACT(MONTH FROM timestamp)
                ORDER BY month
            """, (year,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'month': int(row[0]),
                    'electricity_consumed_kwh': round((row[2] or 0) - (row[1] or 0), 2),
                    'electricity_produced_kwh': round((row[4] or 0) - (row[3] or 0), 2),
                    'gas_consumed_m3': round((row[6] or 0) - (row[5] or 0), 2)
                })
            
            return results
        finally:
            if cursor:
                cursor.close()
        
    def export_to_json(self, data, filename):
        """Export data to JSON file"""
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Report exported to {filename}")
        
    def export_to_csv(self, data, filename):
        """Export data to CSV file"""
        if not data:
            print("No data to export")
            return
            
        with open(filename, 'w', newline='') as f:
            if isinstance(data, list) and len(data) > 0:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            else:
                writer = csv.DictWriter(f, fieldnames=data.keys())
                writer.writeheader()
                writer.writerow(data)
        print(f"Report exported to {filename}")


def main():
    parser = argparse.ArgumentParser(description='Generate HomeWizard consumption reports')
    parser.add_argument('--year', type=int, default=datetime.now().year,
                       help='Year to generate report for (default: current year)')
    parser.add_argument('--monthly', action='store_true',
                       help='Generate monthly breakdown')
    parser.add_argument('--format', choices=['json', 'csv', 'console'], default='console',
                       help='Output format (default: console)')
    parser.add_argument('--output', help='Output filename (only for json/csv formats)')
    
    args = parser.parse_args()
    
    # Validate year
    if args.year < 2000 or args.year > 2100:
        print(f"Error: Year must be between 2000 and 2100, got {args.year}", file=sys.stderr)
        sys.exit(1)
    
    # Load database configuration from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'homewizard')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'postgres')
    
    generator = None
    try:
        generator = ReportGenerator(db_host, db_port, db_name, db_user, db_password)
        
        if args.monthly:
            data = generator.get_monthly_consumption(args.year)
            title = f"Monthly Report {args.year}"
        else:
            data = generator.get_yearly_consumption(args.year)
            title = f"Yearly Report {args.year}"
            
        if not data:
            print(f"No data available for year {args.year}")
            return
            
        if args.format == 'console':
            print(f"\n=== {title} ===")
            if args.monthly:
                for month_data in data:
                    print(f"\nMonth {month_data['month']}:")
                    print(f"  Electricity Consumed: {month_data['electricity_consumed_kwh']} kWh")
                    print(f"  Electricity Produced: {month_data['electricity_produced_kwh']} kWh")
                    print(f"  Gas Consumed: {month_data['gas_consumed_m3']} m³")
            else:
                print(f"Electricity Consumed: {data['electricity_consumed_kwh']} kWh")
                print(f"Electricity Produced: {data['electricity_produced_kwh']} kWh")
                print(f"Gas Consumed: {data['gas_consumed_m3']} m³")
                print(f"Measurements: {data['measurement_count']}")
            print("========================\n")
        elif args.format == 'json':
            filename = args.output or f"report_{args.year}{'_monthly' if args.monthly else ''}.json"
            generator.export_to_json(data, filename)
        elif args.format == 'csv':
            filename = args.output or f"report_{args.year}{'_monthly' if args.monthly else ''}.csv"
            generator.export_to_csv(data, filename)
        
    except RuntimeError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except psycopg2.ProgrammingError as e:
        print(f"Database query error: {e}", file=sys.stderr)
        sys.exit(1)
    except psycopg2.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if generator:
            generator.close()


if __name__ == '__main__':
    main()
