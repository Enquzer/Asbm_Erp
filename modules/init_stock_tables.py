from app import app, db
from modules.stock_models import DutyStation, Location, Category, Subcategory, Item, Stock, Transaction, FixedAsset, Product
from datetime import datetime

def init_stock_tables():
    with app.app_context():
        # Create new tables (won't affect existing tables)
        db.create_all()

        # Check if Duty Stations already exist to avoid duplicates
        if not DutyStation.query.first():
            duty_stations = [
                DutyStation(duty_station_name='Sendafa'),
                DutyStation(duty_station_name='Mojo'),
                DutyStation(duty_station_name='HO'),
                DutyStation(duty_station_name='Kality'),
                DutyStation(duty_station_name='EBA'),
                DutyStation(duty_station_name='Addis Ababa')
            ]
            db.session.bulk_save_objects(duty_stations)
            db.session.commit()

        # Insert Locations
        if not Location.query.first():
            locations = [
                Location(location_name='Store (Assessories)', duty_station_id=1),
                Location(location_name='Store (Finished/Different)', duty_station_id=1),
                Location(location_name='Store (Finished/Fabric)', duty_station_id=1),
                Location(location_name='Store (Spinning floor)', duty_station_id=1),
                Location(location_name='Spinning Dept', duty_station_id=1),
                Location(location_name='Dyeing', duty_station_id=2),
                Location(location_name='Spinning', duty_station_id=5),
                Location(location_name='Production Dept', duty_station_id=4),
                Location(location_name='Store', duty_station_id=3)
            ]
            db.session.bulk_save_objects(locations)
            db.session.commit()

        # Insert Categories
        if not Category.query.first():
            categories = [
                Category(category_name='Accessories'),
                Category(category_name='Raw Materials'),
                Category(category_name='Finished Goods'),
                Category(category_name='Tools'),
                Category(category_name='Packaging Materials')
            ]
            db.session.bulk_save_objects(categories)
            db.session.commit()

        # Insert Subcategories
        if not Subcategory.query.first():
            subcategories = [
                Subcategory(subcategory_name='Thread', category_id=1),
                Subcategory(subcategory_name='Button', category_id=1),
                Subcategory(subcategory_name='Zipper', category_id=1),
                Subcategory(subcategory_name='Chemical', category_id=2),
                Subcategory(subcategory_name='Fabric', category_id=2),
                Subcategory(subcategory_name='Cotton', category_id=2),
                Subcategory(subcategory_name='Yarn', category_id=2),
                Subcategory(subcategory_name='Towel', category_id=2),
                Subcategory(subcategory_name='Bedding', category_id=3),
                Subcategory(subcategory_name='Apparel', category_id=3),
                Subcategory(subcategory_name='Hand Tools', category_id=4),
                Subcategory(subcategory_name='Power Tools', category_id=4),
                Subcategory(subcategory_name='Boxes', category_id=5)
            ]
            db.session.bulk_save_objects(subcategories)
            db.session.commit()

        # Map existing Products to Items (if Products table exists)
        products = Product.query.all()
        for product in products:
            if not Item.query.filter_by(product_id=product.product_id).first():
                item = Item(
                    item_name=product.product_name,
                    item_description=product.product_name,
                    unit_of_measurement='unit',  # Default UoM, adjust as needed
                    product_id=product.product_id
                )
                db.session.add(item)
        db.session.commit()

        # Insert additional Items
        if not Item.query.filter_by(item_name='Black Thread').first():
            items = [
                Item(item_name='Black Thread', item_description='Black Thread', unit_of_measurement='Cone', subcategory_id=1, unit_price=73),
                Item(item_name='Brown Button', item_description='Brown Button', unit_of_measurement='Gross', subcategory_id=2, unit_price=110),
                Item(item_name='Black Zipper', item_description='Black Zipper', unit_of_measurement='Pcs', subcategory_id=3),
                Item(item_name='Reactive Black B', item_description='Reactive Black B', unit_of_measurement='Kg', subcategory_id=4, unit_price=1300),
                Item(item_name='Jeans Demin Fabric', item_description='Jeans Denim Fabric', unit_of_measurement='Mtr', subcategory_id=5),
                Item(item_name='Lint Cotton', item_description='Lint Cotton', unit_of_measurement='Kg', subcategory_id=6, unit_price=145),
                Item(item_name='20/1 OE ASBM Yarn', item_description='20/1 OE ASBM Yarn', unit_of_measurement='Kg', subcategory_id=7),
                Item(item_name='Towel 90 * 180', item_description='Towel 90 x 180', unit_of_measurement='Kg', subcategory_id=8),
                Item(item_name='Bed Sheet Light Blue', item_description='Bed Sheet Light Blue', unit_of_measurement='Mtr', subcategory_id=9),
                Item(item_name='Driver Male Jacket & Trouser (Tele)', item_description='Driver Male Jacket & Trouser (Tele)', unit_of_measurement='Set', subcategory_id=10),
                Item(item_name='Screwdriver', item_description='Phillips head screwdriver', unit_of_measurement='Pcs', subcategory_id=11, unit_price=10.0),
                Item(item_name='Hammer', item_description='Claw hammer', unit_of_measurement='Pcs', subcategory_id=11, unit_price=15.0),
                Item(item_name='Electric Drill', item_description='Cordless drill', unit_of_measurement='Pcs', subcategory_id=12, unit_price=50.0),
                Item(item_name='Cardboard Box', item_description='Standard shipping box', unit_of_measurement='Pcs', subcategory_id=13, unit_price=5.0)
            ]
            db.session.bulk_save_objects(items)
            db.session.commit()

        # Insert Transactions
        if not Transaction.query.first():
            transactions = [
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=1, location_id=1, condition='Used', quantity=85, total_value=6205, remarks='Used'),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=2, location_id=1, quantity=189, total_value=20790),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=3, location_id=1, quantity=48),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=4, location_id=2, quantity=6050, total_value=7865000),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=5, location_id=3, quantity=40),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=6, location_id=4, quantity=12240, total_value=1989400),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=7, location_id=4, quantity=3109.62),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=8, location_id=3, quantity=0),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=9, location_id=3, quantity=554.16),
                Transaction(transaction_date=datetime(2024, 7, 1), transaction_type='INITIAL', item_id=10, location_id=3, quantity=651),
                Transaction(transaction_date=datetime(2025, 3, 22), transaction_type='INITIAL', item_id=11, location_id=1, condition='New', quantity=50, total_value=500, remarks='Sendafa store'),
                Transaction(transaction_date=datetime(2025, 3, 22), transaction_type='INITIAL', item_id=12, location_id=1, condition='New', quantity=30, total_value=450, remarks='Sendafa store'),
                Transaction(transaction_date=datetime(2025, 3, 22), transaction_type='INITIAL', item_id=13, location_id=6, condition='New', quantity=10, total_value=500, remarks='Mojo dyeing'),
                Transaction(transaction_date=datetime(2025, 3, 22), transaction_type='INITIAL', item_id=14, location_id=6, condition='New', quantity=1000, total_value=5000, remarks='Mojo store'),
                Transaction(transaction_date=datetime(2024, 7, 31), transaction_type='IN', item_id=4, location_id=2, quantity=3200, total_value=4160000),
                Transaction(transaction_date=datetime(2024, 7, 31), transaction_type='OUT', item_id=4, location_id=2, quantity=1125, total_value=1462500),
                Transaction(transaction_date=datetime(2025, 3, 23), transaction_type='OUT', item_id=14, location_id=6, condition='New', quantity=200, total_value=1000, remarks='Used for shipping'),
                Transaction(transaction_date=datetime(2025, 3, 23), transaction_type='OUT', item_id=14, location_id=6, condition='New', quantity=200, total_value=1000)
            ]
            db.session.bulk_save_objects(transactions)
            db.session.commit()

        # Update Stock
        if not Stock.query.first():
            from sqlalchemy import func
            stock_data = db.session.query(
                Transaction.item_id,
                Transaction.location_id,
                Transaction.condition,
                func.sum(
                    func.iif(Transaction.transaction_type.in_(['INITIAL', 'IN', 'PRODUCTION', 'PURCHASE']), Transaction.quantity, -Transaction.quantity)
                ).label('quantity'),
                func.max(Transaction.transaction_date).label('last_updated')
            ).group_by(Transaction.item_id, Transaction.location_id, Transaction.condition).all()

            stocks = [
                Stock(item_id=row.item_id, location_id=row.location_id, condition=row.condition, quantity=row.quantity, last_updated=row.last_updated)
                for row in stock_data
            ]
            db.session.bulk_save_objects(stocks)
            db.session.commit()

        # Insert Fixed Assets
        if not FixedAsset.query.first():
            fixed_assets = [
                FixedAsset(asset_name='Single Needle Machine', brand='AOTORI', model='ATR-9803', serial_number='201404022', location_id=8),
                FixedAsset(asset_name='Steam Boiler 2 Ton Each Boiler', location_id=6),
                FixedAsset(asset_name='Vamatex Tawol SELVER DI', serial_number='074425', location_id=7),
                FixedAsset(asset_name='Forklift', brand='Toyota', model='7FGU25', serial_number='FL12345', location_id=6, remarks='Newly purchased')
            ]
            db.session.bulk_save_objects(fixed_assets)
            db.session.commit()

if __name__ == '__main__':
    init_stock_tables()
    print("Stock management tables initialized successfully.")a