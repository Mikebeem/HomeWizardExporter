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
from psycopg2 import sql


class ReportGenerator:
    """Generate consumption reports"""
    
    def __init__(self, host, port, database, user, password):
        self.connection = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
    def close(self):
        """Close database connection"""
        self.connection.close()
        
    def get_yearly_consumption(self, year):
        """Get yearly consumption statistics"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT 
                MIN(total_imported) as start_imported,
                MAX(total_imported) as end_imported,
                MIN(total_exported) as start_exported,
                MAX(total_exported) as end_exported,
                MIN(gas_total_m3) as start_gas,
                MAX(gas_total_m3) as end_gas,
                COUNT(*) as measurement_count
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
                'gas_consumed_m3': round((result[5] or 0) - (result[4] or 0), 2),
                'measurement_count': result[6]
            }
        return None
        
    def get_monthly_consumption(self, year):
        """Get monthly consumption statistics for a year"""
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
        
        cursor.close()
        return results
        
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
    
    # Load database configuration from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'homewizard')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'postgres')
    
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
            generator.close()
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
            
        generator.close()
        
    except psycopg2.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
