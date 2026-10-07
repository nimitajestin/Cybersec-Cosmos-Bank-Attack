-- Educational seed matching core/database.py (the app also auto-seeds on first run).
-- All banks, cards, ATMs, and amounts are fictional.

INSERT OR IGNORE INTO accounts (card, holder_name, available_balance, original_balance, country, status) VALUES
('XXXX-XXXX-1001', 'A. Kulkarni (fictional)', 50000.0, 50000.0, 'India', 'ACTIVE'),
('XXXX-XXXX-2847', 'S. Mehta (fictional)', 12000.0, 12000.0, 'India', 'ACTIVE'),
('XXXX-XXXX-3391', 'R. Iyer (fictional)', 250000.0, 250000.0, 'India', 'ACTIVE'),
('XXXX-XXXX-4520', 'N. Sharma (fictional)', 8500.0, 8500.0, 'India', 'ACTIVE'),
('XXXX-XXXX-6677', 'P. Deshmukh (fictional)', 120000.0, 120000.0, 'India', 'ACTIVE'),
('XXXX-XXXX-8901', 'K. Banerjee (fictional)', 3200.0, 3200.0, 'India', 'ACTIVE'),
('XXXX-XXXX-SW01', 'Nostro Settlement Desk (fictional)', 500000000.0, 500000000.0, 'India', 'ACTIVE');

INSERT OR IGNORE INTO atms (atm_id, country, city, status) VALUES
('IN-PUN-001', 'India', 'Pune', 'ONLINE'),
('IN-MUM-014', 'India', 'Mumbai', 'ONLINE'),
('AE-DXB-003', 'UAE', 'Dubai', 'ONLINE'),
('AE-AUH-007', 'UAE', 'Abu Dhabi', 'ONLINE'),
('TH-BKK-021', 'Thailand', 'Bangkok', 'ONLINE'),
('TH-CHM-009', 'Thailand', 'Chiang Mai', 'ONLINE'),
('MY-KUL-011', 'Malaysia', 'Kuala Lumpur', 'ONLINE'),
('MY-JHB-004', 'Malaysia', 'Johor Bahru', 'ONLINE');
