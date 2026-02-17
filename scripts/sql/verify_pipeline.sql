.headers on
.mode column

SELECT 'runs' AS table_name, COUNT(*) AS count FROM runs;
SELECT 'products' AS table_name, COUNT(*) AS count FROM products;
SELECT 'product_snapshots' AS table_name, COUNT(*) AS count FROM product_snapshots;

SELECT id, source, status, fetched_at, created_at, error
FROM runs
ORDER BY id DESC
LIMIT 10;

SELECT p.name, p.url, s.votes_count, s.observed_at
FROM product_snapshots s
JOIN products p ON p.id = s.product_id
ORDER BY s.id DESC
LIMIT 20;
