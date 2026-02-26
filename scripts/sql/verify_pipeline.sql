.headers on
.mode column

-- Total observations stored
SELECT COUNT(*) AS total_observations FROM products;

-- Most recent 10 observations
SELECT name, votes, url, tags, observed_at
FROM products
ORDER BY observed_at DESC, votes DESC
LIMIT 10;

-- Top 10 products by votes across all observations
SELECT name, MAX(votes) AS peak_votes, COUNT(*) AS times_seen, MIN(observed_at) AS first_seen
FROM products
GROUP BY url
ORDER BY peak_votes DESC
LIMIT 10;
