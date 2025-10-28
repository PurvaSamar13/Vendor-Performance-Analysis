import sqlite3
import pandas as pd
import logging
import os
from ingestion_db import ingest_db
from sqlalchemy import create_engine

# Ensure logs folder exists
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/get_vendor_summary.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a"
)

def create_vendor_summary(conn):
    query = """
    WITH 
    FreightSummary AS (
        SELECT VendorNumber, SUM(Freight) AS FreightCost
        FROM vendor_invoice
        GROUP BY VendorNumber
    ),
    PurchaseSummary AS (
        SELECT 
            p.VendorNumber,
            p.Brand,
            p.VendorName,
            p.Description,
            p.PurchasePrice,
            pp.PurchasePrice AS ActualPrice,
            pp.Volume,
            SUM(p.Quantity) AS TotalPurchaseQuantity,
            SUM(p.Dollars) AS TotalPurchaseDollars
        FROM purchases p
        JOIN purchase_prices pp ON p.Brand = pp.Brand
        WHERE p.PurchasePrice > 0
        GROUP BY 
            p.VendorNumber, p.Brand, p.VendorName, 
            p.Description, p.PurchasePrice, pp.PurchasePrice, pp.Volume
    ),
    SalesSummary AS (
        SELECT 
            VendorNo, Brand,
            SUM(SalesQuantity) AS TotalSalesQuantity,
            SUM(SalesDollars) AS TotalSalesDollars,
            SUM(SalesPrice) AS TotalSalesPrice,
            SUM(ExciseTax) AS TotalExciseTax
        FROM sales
        GROUP BY VendorNo, Brand
    )
    SELECT 
        ps.VendorNumber,
        ps.VendorName,
        ps.Brand,
        ps.Description,
        ps.PurchasePrice,
        ps.ActualPrice,
        ps.Volume,
        ps.TotalPurchaseQuantity,
        ps.TotalPurchaseDollars,
        ss.TotalSalesQuantity,
        ss.TotalSalesDollars,
        ss.TotalSalesPrice,
        ss.TotalExciseTax,
        fs.FreightCost
    FROM PurchaseSummary ps
    LEFT JOIN SalesSummary ss ON ps.VendorNumber = ss.VendorNo AND ps.Brand = ss.Brand
    LEFT JOIN FreightSummary fs ON ps.VendorNumber = fs.VendorNumber
    ORDER BY ps.TotalPurchaseDollars DESC
    """
    return pd.read_sql_query(query, conn)


def clean_data(df):
    df['Volume'] = df['Volume'].astype('float64')
    df.fillna(0, inplace=True)
    df['VendorName'] = df['VendorName'].str.strip()
    df['Description'] = df['Description'].str.strip()

    df['GrossProfit'] = df['TotalSalesDollars'] - df['TotalPurchaseDollars']
    df['ProfitMargin'] = (df['GrossProfit'] / df['TotalSalesDollars'].replace(0, pd.NA)) * 100
    df['StockTurnover'] = df['TotalSalesQuantity'] / df['TotalPurchaseQuantity'].replace(0, pd.NA)
    df['SalestoPurchaseRatio'] = df['TotalSalesDollars'] / df['TotalPurchaseDollars'].replace(0, pd.NA)
    return df


if __name__ == '__main__':
    conn = sqlite3.connect('inventory.db')
    engine = create_engine('sqlite:///inventory.db')

    logging.info("Starting Vendor Summary creation...")

    summary_df = create_vendor_summary(conn)
    logging.info("Vendor Summary created successfully. Shape: %s", summary_df.shape)
    logging.info("\nSample data:\n%s", summary_df.head().to_string())

    clean_df = clean_data(summary_df)
    logging.info("Data cleaned successfully. Columns: %s", list(clean_df.columns))

    ingest_db(clean_df, 'vendor_sales_summary', engine)
    logging.info("Data ingestion completed successfully.")
