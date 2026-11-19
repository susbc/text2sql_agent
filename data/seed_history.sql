-- ============================================================
-- seed_history.sql — 应用表种子（6 表，50 行）
-- 源：MySQL business_db（只读迁移）。
-- 由 scripts/migrate_mysql_to_sqlite.py 生成；请勿手工编辑，重跑脚本可再生成。
-- 类型映射（spec §5.1）：INTEGER/TEXT/NUMERIC/REAL；去 COLLATE/ENGINE/COMMENT。
-- 注：sql_generation_history.sql_dialect 新行默认 'sqlite'（spec §5.4），
--     迁移旧行忠实保留源值 'mysql'。
-- 注：ON UPDATE CURRENT_TIMESTAMP 已去除；应用层 UPDATE 显式置
--     updated_at=CURRENT_TIMESTAMP（行为不变）。
-- ============================================================


-- ------------------------------------------------------------
-- sql_generation_history — SQL 生成历史表（50 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sql_generation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_query TEXT NOT NULL,
    generated_sql TEXT,
    sql_dialect TEXT DEFAULT 'sqlite',
    semantic_datasource TEXT,
    semantic_dialect TEXT,
    semantic_version TEXT,
    semantic_content_sha256 TEXT,
    governance_validated INTEGER NOT NULL DEFAULT 0,
    validation_status TEXT DEFAULT 'pending',
    validation_error TEXT,
    execution_status TEXT DEFAULT 'pending',
    execution_error TEXT,
    execution_result TEXT,
    matched_knowledge TEXT,
    retrieval_query TEXT,
    feedback_score INTEGER,
    feedback_comment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_created_at ON sql_generation_history (created_at);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_execution_status ON sql_generation_history (execution_status);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_governed_few_shot ON sql_generation_history (governance_validated, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, validation_status, execution_status, created_at);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_session ON sql_generation_history (session_id);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_validation_status ON sql_generation_history (validation_status);
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (1, '595978d3-f092-4474-a687-7a1f5b7626ed', '测试查询', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'pass', NULL, 'pending', NULL, NULL, NULL, NULL, NULL, NULL, '2026-03-21 18:36:51', '2026-03-21 18:36:51');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (2, 'f6877ca9-5bf9-4269-8472-5a365c2f2ed8', '测试查询', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'pass', NULL, 'pending', NULL, NULL, NULL, NULL, NULL, NULL, '2026-03-21 18:38:38', '2026-03-21 18:38:38');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (3, 'a9f41b4d-31d5-4809-9a1d-e0f0ec2f7252', '测试查询', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'pass', NULL, 'pending', NULL, NULL, NULL, NULL, NULL, NULL, '2026-03-21 21:24:38', '2026-03-21 21:24:38');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (4, '0ce74a66-8ae1-435d-81a3-3667466fbb51', '测试查询', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'pass', NULL, 'pending', NULL, NULL, NULL, NULL, NULL, NULL, '2026-03-22 15:37:10', '2026-03-22 15:37:10');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (5, '5b3f4820-e6c7-4f66-bed4-ca304b3a27fd', '统计每个用户的订单数量和总金额，按金额降序排序', 'SELECT u.id, u.username, COUNT(o.id) AS order_count, SUM(o.amount) AS total_amount
FROM orders o
LEFT JOIN users u ON o.user_id = u.id
GROUP BY u.id, u.username
ORDER BY total_amount DESC', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '统计每个用户的订单数量和总金额，按金额降序排序', NULL, NULL, '2026-03-25 14:11:31', '2026-03-25 14:11:31');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (6, 'f05906ad-2f64-459a-af65-2cd4ea2dad7b', '统计每个用户的订单数量和总金额，按金额降序排序', 'SELECT u.id, u.username, COUNT(o.id) AS order_count, SUM(o.amount) AS total_amount
FROM orders o
JOIN users u ON o.user_id = u.id
GROUP BY u.id, u.username
ORDER BY total_amount DESC', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '统计每个用户的订单数量和总金额，按金额降序排序', NULL, NULL, '2026-03-25 14:13:35', '2026-03-25 14:13:35');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (7, 'a35a54b8-25d3-47e4-8db2-66bb42e16e6e', '查询每个用户的订单数量和平均订单金额，只显示订单数大于 2 的用户', 'SELECT 
    u.id AS user_id,
    u.username,
    COUNT(o.id) AS order_count,
    AVG(o.amount) AS average_order_amount
FROM 
    users u
INNER JOIN 
    orders o ON u.id = o.user_id
GROUP BY 
    u.id, u.username
HAVING 
    COUNT(o.id) > 2', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询每个用户的订单数量和平均订单金额，只显示订单数大于 2 的用户', NULL, NULL, '2026-03-25 14:32:52', '2026-03-25 14:32:52');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (8, '808340a9-c964-4dfa-be9d-13eb0b10a602', '统计最近 30 天每天的订单数量和总金额', 'SELECT 
    DATE(created_at) AS date,
    COUNT(*) AS order_count,
    SUM(amount) AS total_amount
FROM 
    orders
WHERE 
    created_at >= NOW() - INTERVAL 30 DAY
GROUP BY 
    DATE(created_at)
ORDER BY 
    date', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '统计最近 30 天每天的订单数量和总金额', NULL, NULL, '2026-03-25 14:33:30', '2026-03-25 14:33:30');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (9, '21911fb1-9b24-4989-848b-c18bb988b7b8', '查询订单金额高于平均订单金额的所有订单', 'SELECT 
    id, 
    order_no, 
    amount, 
    created_at
FROM 
    orders
WHERE 
    amount > (SELECT AVG(amount) FROM orders)', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询订单金额高于平均订单金额的所有订单', NULL, NULL, '2026-03-25 14:33:52', '2026-03-25 14:33:52');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (10, '555ffe4b-ab3d-4335-8a6b-d35680afe700', '查询所有用户', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询所有用户', NULL, NULL, '2026-03-25 15:13:22', '2026-03-25 15:13:22');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (11, '2b460348-9440-4259-aaa6-542f975c4258', '统计每个用户的订单数量和总金额', 'SELECT u.id, u.username, COUNT(o.id) AS order_count, SUM(o.amount) AS total_amount
FROM users u
INNER JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.username', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '统计每个用户的订单数量和总金额', NULL, NULL, '2026-03-25 15:59:27', '2026-03-25 15:59:27');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (12, '4d0252f2-1143-4875-af78-cc0caa0a8d92', '查询所有用户', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询所有用户', NULL, NULL, '2026-03-25 15:59:33', '2026-03-25 15:59:33');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (13, 'b90c4ee0-52c5-43e5-9666-ff6340cbd595', '统计订单数量', 'SELECT COUNT(*) FROM orders', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '统计订单数量', NULL, NULL, '2026-03-25 15:59:36', '2026-03-25 15:59:36');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (14, 'fe0c5587-6863-4d92-91b0-dcec27947ed2', '查询金额最大的订单', 'SELECT id, order_no, amount, status, created_at
FROM orders
ORDER BY amount DESC
LIMIT 1', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询金额最大的订单', NULL, NULL, '2026-03-25 15:59:37', '2026-03-25 15:59:37');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (15, 'd10b9035-f107-4bad-a074-b27c6f4fa983', '查询所有用户', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "users", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "customer_account", "score": 0.2369, "node_id": null, "node_type": "table"}, {"name": "user_credit_report", "score": 0.2275, "node_id": null, "node_type": "table"}, {"name": "credit_query_records", "score": 0.2149, "node_id": null, "node_type": "table"}, {"name": "customer_sessions", "score": 0.181, "node_id": null, "node_type": "table"}]', '查询所有用户', NULL, NULL, '2026-03-25 17:04:15', '2026-03-25 17:04:15');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (16, 'd10b9035-f107-4bad-a074-b27c6f4fa983', '查询金额最大的订单', 'SELECT * 
FROM orders 
ORDER BY amount DESC 
LIMIT 1', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "credit_query_records", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "business_transaction", "score": 0.2578, "node_id": null, "node_type": "table"}, {"name": "customer_account", "score": 0.2509, "node_id": null, "node_type": "table"}, {"name": "bank_customer", "score": 0.2093, "node_id": null, "node_type": "table"}, {"name": "credit_card_records", "score": 0.1889, "node_id": null, "node_type": "table"}]', '查询金额最大的订单', NULL, NULL, '2026-03-25 17:04:43', '2026-03-25 17:04:43');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (17, 'd10b9035-f107-4bad-a074-b27c6f4fa983', '查询创建时间最近的订单', 'SELECT * 
FROM orders 
ORDER BY created_at DESC 
LIMIT 1', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "credit_query_records", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "customer_account", "score": 0.2739, "node_id": null, "node_type": "table"}, {"name": "customer_sessions", "score": 0.2373, "node_id": null, "node_type": "table"}, {"name": "corporate_customer", "score": 0.2083, "node_id": null, "node_type": "table"}, {"name": "credit_public_records", "score": 0.1895, "node_id": null, "node_type": "table"}]', '查询创建时间最近的订单', NULL, NULL, '2026-03-25 17:06:10', '2026-03-25 17:06:10');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (18, 'd10b9035-f107-4bad-a074-b27c6f4fa983', '查询金额最大的订单所属用户的账户信息', 'SELECT u.*
FROM users u
JOIN (
    SELECT user_id
    FROM orders
    ORDER BY amount DESC
    LIMIT 1
) o ON u.id = o.user_id', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "customer_account", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "bank_customer", "score": 0.2144, "node_id": null, "node_type": "table"}, {"name": "credit_query_records", "score": 0.2005, "node_id": null, "node_type": "table"}, {"name": "user_credit_report", "score": 0.1801, "node_id": null, "node_type": "table"}, {"name": "customer_sessions", "score": 0.1735, "node_id": null, "node_type": "table"}]', '查询金额最大的订单所属用户的账户信息', NULL, NULL, '2026-03-25 17:10:19', '2026-03-25 17:10:19');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (19, 'd10b9035-f107-4bad-a074-b27c6f4fa983', '查询金额最大的订单所属用户的账户下，每张卡的余额', 'SELECT ccr.card_number, ccr.balance
FROM orders o
JOIN (
    SELECT user_id
    FROM orders
    ORDER BY amount DESC
    LIMIT 1
) max_order ON o.user_id = max_order.user_id
JOIN users u ON u.id = o.user_id
JOIN customer_account ca ON ca.user_id = u.id
JOIN credit_card_records ccr ON ccr.account_id = ca.account_id', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "customer_account", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "credit_card_records", "score": 0.2898, "node_id": null, "node_type": "table"}, {"name": "bank_customer", "score": 0.2719, "node_id": null, "node_type": "table"}, {"name": "credit_query_records", "score": 0.2338, "node_id": null, "node_type": "table"}, {"name": "user_credit_report", "score": 0.2215, "node_id": null, "node_type": "table"}]', '查询金额最大的订单所属用户的账户下，每张卡的余额', NULL, NULL, '2026-03-25 17:11:51', '2026-03-25 17:11:51');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (20, 'd10b9035-f107-4bad-a074-b27c6f4fa983', '查询创建时间最近的订单所属用户的每张卡的余额', 'SELECT ccr.card_number, ccr.balance
FROM orders o
JOIN (
    SELECT user_id
    FROM orders
    ORDER BY created_at DESC
    LIMIT 1
) recent_order ON o.user_id = recent_order.user_id
JOIN users u ON u.id = o.user_id
JOIN customer_account ca ON ca.user_id = u.id
JOIN credit_card_records ccr ON ccr.account_id = ca.account_id', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "credit_card_records", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "customer_account", "score": 0.2719, "node_id": null, "node_type": "table"}, {"name": "credit_query_records", "score": 0.2195, "node_id": null, "node_type": "table"}, {"name": "bank_customer", "score": 0.2142, "node_id": null, "node_type": "table"}, {"name": "customer_sessions", "score": 0.2055, "node_id": null, "node_type": "table"}]', '查询创建时间最近的订单所属用户的每张卡的余额', NULL, NULL, '2026-03-25 17:48:55', '2026-03-25 17:48:55');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (21, '0c57f1d3-f176-4b42-bfcc-0c270b650c97', '查询金额最大的订单', 'SELECT id, user_id, order_no, amount, status, created_at
FROM orders
ORDER BY amount DESC
LIMIT 1', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "credit_query_records", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "business_transaction", "score": 0.2578, "node_id": null, "node_type": "table"}, {"name": "customer_account", "score": 0.2509, "node_id": null, "node_type": "table"}, {"name": "bank_customer", "score": 0.2093, "node_id": null, "node_type": "table"}, {"name": "credit_card_records", "score": 0.1889, "node_id": null, "node_type": "table"}]', '查询金额最大的订单', NULL, NULL, '2026-03-25 21:50:59', '2026-03-25 21:50:59');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (22, '0c57f1d3-f176-4b42-bfcc-0c270b650c97', '查询金额最大的订单，并统计该订单对应的用户账户总金额', 'SELECT SUM(o.amount) AS total_amount
FROM orders o
WHERE o.user_id = (
    SELECT o.user_id
    FROM orders o
    ORDER BY o.amount DESC
    LIMIT 1
)', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "customer_account", "score": 0.3, "node_id": null, "node_type": "table"}, {"name": "credit_query_records", "score": 0.2341, "node_id": null, "node_type": "table"}, {"name": "bank_customer", "score": 0.2104, "node_id": null, "node_type": "table"}, {"name": "user_credit_report", "score": 0.2065, "node_id": null, "node_type": "table"}, {"name": "business_transaction", "score": 0.2056, "node_id": null, "node_type": "table"}]', '查询金额最大的订单，并统计该订单对应的用户账户总金额', NULL, NULL, '2026-03-25 21:54:43', '2026-03-25 21:54:43');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (23, '4168c4ab-d19d-4718-bcac-ff1945372dba', '查询所有用户', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询所有用户', NULL, NULL, '2026-03-26 14:02:30', '2026-03-26 14:02:30');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (24, '213a7290-1f7c-4e7d-9f78-4cab640c39dc', '查询订单数量
', 'SELECT COUNT(*) AS order_count FROM orders', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询订单数量
', NULL, NULL, '2026-03-26 14:11:37', '2026-03-26 14:11:37');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (25, 'a137dfa7-b551-46a5-a04b-11876a418a99', '查询当前持有 R3 风险等级理财产品的用户总数，以及这些用户的平均账户余额', '-- 假设的表结构
-- financial_products (id, name, risk_level)
-- user_financial_products (user_id, product_id)
-- users (id, balance)

SELECT 
    COUNT(DISTINCT u.id) AS total_users,
    AVG(u.balance) AS average_balance
FROM 
    users u
JOIN 
    user_financial_products ufp ON u.id = ufp.user_id
JOIN 
    financial_products fp ON ufp.product_id = fp.id
WHERE 
    fp.risk_level = ''R3''', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询当前持有 R3 风险等级理财产品的用户总数，以及这些用户的平均账户余额', NULL, NULL, '2026-03-30 00:17:04', '2026-03-30 00:17:04');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (26, 'a137dfa7-b551-46a5-a04b-11876a418a99', '查询金额最大的订单', 'SELECT *
FROM orders
ORDER BY amount DESC
LIMIT 1', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询金额最大的订单', NULL, NULL, '2026-03-30 00:17:35', '2026-03-30 00:17:35');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (27, 'b3ba6b40-a1d8-4af1-a497-00ce5882cd24', '查询所有用户', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询所有用户', NULL, NULL, '2026-03-31 21:01:08', '2026-03-31 21:01:08');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (28, '911e7986-89ed-47c8-89ac-34c4e1ce5bae', '查询近半年参与过新用户立减活动的用户总数，以及这些用户的平均月下单次数', 'WITH recent_activity_users AS (
    SELECT 
        user_id
    FROM 
        activity_user_join
    WHERE 
        activity_type = ''新用户立减活动''
        AND join_time >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
),
user_orders AS (
    SELECT 
        o.user_id,
        COUNT(o.id) AS order_count
    FROM 
        orders o
    JOIN 
        recent_activity_users rau ON o.user_id = rau.user_id
    WHERE 
        o.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
    GROUP BY 
        o.user_id
)
SELECT 
    COUNT(DISTINCT rau.user_id) AS user_count,
    AVG(uo.order_count / 6) AS avg_monthly_order_count
FROM 
    recent_activity_users rau
LEFT JOIN 
    user_orders uo ON rau.user_id = uo.user_id', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "coupon_user_receive", "score": 0.4, "node_id": null, "node_type": "table"}, {"name": "coupon_user_use", "score": 0.3929, "node_id": null, "node_type": "table"}, {"name": "coupon_main", "score": 0.3116, "node_id": null, "node_type": "table"}, {"name": "activity_user_join", "score": 0.3076, "node_id": null, "node_type": "table"}, {"name": "ins_premium_payment", "score": 0.286, "node_id": null, "node_type": "table"}]', '查询近半年参与过新用户立减活动的用户总数，以及这些用户的平均月下单次数', NULL, NULL, '2026-04-01 14:03:18', '2026-04-01 14:03:18');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (29, 'dbdc33ff-c139-4059-b5d6-7b7d4359ba44', '统计本月每个司机的用户投诉量，按投诉量从高到低排序', 'SELECT 
  driver_id, 
  COUNT(*) AS complaint_count
FROM 
  complaints
WHERE 
  DATE_TRUNC(''month'', complaint_date) = DATE_TRUNC(''month'', CURRENT_DATE)
GROUP BY 
  driver_id
ORDER BY 
  complaint_count DESC', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '统计本月每个司机的用户投诉量，按投诉量从高到低排序', NULL, NULL, '2026-04-01 14:31:42', '2026-04-01 14:31:42');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (30, '869c7fce-06ba-4302-8305-53b34232f865', '测试查询', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'pass', NULL, 'pending', NULL, NULL, NULL, NULL, NULL, NULL, '2026-04-12 17:13:08', '2026-04-12 17:13:08');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (31, '310b0f2c-1203-4de3-b162-026fde5efd37', '查询订单数量', 'SELECT COUNT(*) AS order_count
FROM order_main', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询订单数量', NULL, NULL, '2026-04-12 17:29:17', '2026-04-12 17:29:17');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (32, '3d1138c8-503c-4005-965e-de147aa68b0a', '测试查询', 'SELECT * FROM users', 'mysql', NULL, NULL, NULL, NULL, 0, 'pass', NULL, 'pending', NULL, NULL, NULL, NULL, NULL, NULL, '2026-04-12 18:14:18', '2026-04-12 18:14:18');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (33, '815581ee-3d45-45a7-bb19-848dc32f616c', '查询所有用户', 'SELECT * FROM bank_customer', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询所有用户', NULL, NULL, '2026-04-12 18:35:39', '2026-04-12 18:35:39');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (34, '815581ee-3d45-45a7-bb19-848dc32f616c', '查询金额最大的订单的用户的存款总金额', 'SELECT SUM(da.balance) AS total_deposit
FROM deposit_account da
LEFT JOIN bank_customer bc ON da.customer_id = bc.customer_id
WHERE da.account_id = (
    SELECT account_id
    FROM deposit_account
    ORDER BY balance DESC
    LIMIT 1
)
GROUP BY da.customer_id', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询金额最大的订单的用户的存款总金额', NULL, NULL, '2026-04-12 18:38:29', '2026-04-12 18:38:29');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (35, 'f10ca806-0502-4cd8-b599-e5ce492aa31a', '查询金额最大的订单的用户的存款总金额', 'WITH MaxOrder AS (
    SELECT user_id
    FROM order_main
    ORDER BY order_amount DESC
    LIMIT 1
),
UserAccounts AS (
    SELECT a.account_id
    FROM acc_account_main a
    JOIN MaxOrder mo ON a.user_id = mo.user_id
)
SELECT SUM(t.trans_amount) AS total_deposit_amount
FROM acc_account_transaction t
JOIN UserAccounts ua ON t.account_id = ua.account_id
WHERE t.trans_type = 1;  -- 假设 trans_type 为 1 表示存款', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询金额最大的订单的用户的存款总金额', NULL, NULL, '2026-04-12 18:44:41', '2026-04-12 18:44:41');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (36, '2f784b23-6022-4fbb-aeb8-2599e392cfc5', '查询金额最大的订单的用户的存款总金额', 'SELECT SUM(da.balance) AS total_deposit
FROM deposit_account da
JOIN (
    SELECT customer_id
    FROM deposit_account
    ORDER BY balance DESC
    LIMIT 1
) max_balance ON da.customer_id = max_balance.customer_id', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询金额最大的订单的用户的存款总金额', NULL, NULL, '2026-04-12 18:47:04', '2026-04-12 18:47:04');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (37, '2f784b23-6022-4fbb-aeb8-2599e392cfc5', '查询金额最大的订单的用户的存款总金额和订单数量', 'SELECT 
    SUM(da.balance) AS total_deposit,
    COUNT(da.account_id) AS order_count
FROM 
    deposit_account da
JOIN (
    SELECT customer_id
    FROM deposit_account
    ORDER BY balance DESC
    LIMIT 1
) max_balance ON da.customer_id = max_balance.customer_id', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询金额最大的订单的用户的存款总金额和订单数量', NULL, NULL, '2026-04-12 18:49:27', '2026-04-12 18:49:27');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (38, '2f784b23-6022-4fbb-aeb8-2599e392cfc5', '查询金额最大的订单的用户的信息和账户信息', 'SELECT 
    bc.customer_name,
    bc.phone,
    bc.id_card,
    da.account_id,
    da.account_type,
    da.balance
FROM 
    deposit_account da
LEFT JOIN 
    bank_customer bc ON da.customer_id = bc.customer_id
WHERE 
    da.account_id = (
        SELECT account_id
        FROM deposit_account
        ORDER BY balance DESC
        LIMIT 1
    )', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, NULL, '查询金额最大的订单的用户的信息和账户信息', NULL, NULL, '2026-04-12 19:50:12', '2026-04-12 19:50:12');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (39, '380febfd-49b6-46cb-a5e9-9fc0f47e4b19', '查询黑名单用户', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'fail', '查询执行失败，请联系管理员并提供错误编号 aff2d85e9ddd47d7afe32e2065832e52', NULL, '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6493, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.3366, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2955, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.2035, "node_id": null, "node_type": "table"}]', '查询黑名单用户', NULL, NULL, '2026-10-25 15:32:47', '2026-10-25 15:39:41');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (64, 'e0b7d526-e82c-4c87-ac05-bc760f2a428a', '查询黑名单用户', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'success', NULL, '{"row_count": 0, "truncated": false, "data_preview": []}', '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6493, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.3366, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2955, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.2035, "node_id": null, "node_type": "table"}]', '查询黑名单用户', NULL, NULL, '2026-10-25 15:48:32', '2026-10-25 15:49:24');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (65, 'c1b6ad08-69b2-47cf-89df-19aeea3ece0c', '查询黑名单用户', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6493, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.3366, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2955, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.2035, "node_id": null, "node_type": "table"}]', '查询黑名单用户', NULL, NULL, '2026-10-25 16:05:29', '2026-10-25 16:05:29');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (66, 'c1b6ad08-69b2-47cf-89df-19aeea3ece0c', '查询黑名单用户', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6493, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.3366, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2955, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.2035, "node_id": null, "node_type": "table"}]', '查询黑名单用户', NULL, NULL, '2026-10-25 16:38:10', '2026-10-25 16:38:10');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (72, 'd4a18fa2-2e89-4e3e-8661-f11471e0ee29', '查询黑名单用户', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6493, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.3366, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2955, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.2035, "node_id": null, "node_type": "table"}]', '查询黑名单用户', NULL, NULL, '2026-10-25 22:16:47', '2026-10-25 22:16:47');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (73, 'c1310f3c-eb48-4aae-946f-af7148568cc0', '查询黑名单用户', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6493, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.3366, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2955, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.2035, "node_id": null, "node_type": "table"}]', '查询黑名单用户', NULL, NULL, '2026-10-25 23:28:38', '2026-10-25 23:28:38');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (74, '7751b687-552c-4c48-a18f-c9b68fe51da5', '查询所有黑名单用户及其加入时间', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'success', NULL, '{"row_count": 0, "truncated": false, "data_preview": []}', '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6719, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.4101, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.301, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2937, "node_id": null, "node_type": "table"}]', '查询所有黑名单用户及其加入时间', NULL, NULL, '2026-10-29 17:37:34', '2026-10-29 17:41:26');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (75, '7751b687-552c-4c48-a18f-c9b68fe51da5', '查询所有黑名单用户及其加入时间', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'success', NULL, '{"row_count": 3, "truncated": false, "data_preview": [{"id": 1, "target_id": "U10004", "is_deleted": 0, "risk_level": 3, "block_scene": "全部交易", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 1, "update_time": "2026-10-29 17:49:03", "block_reason": "反洗钱监测：多笔快进快出交易，命中监管预警模型", "create_operator": "风控系统"}, {"id": 2, "target_id": "6222020000001002", "is_deleted": 0, "risk_level": 2, "block_scene": "提现", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 2, "update_time": "2026-10-29 17:49:03", "block_reason": "疑似套现：同一商户高频大额提现", "create_operator": "风控系统"}, {"id": 3, "target_id": "203.0.113.66", "is_deleted": 0, "risk_level": 1, "block_scene": "转账", "create_time": "2026-10-29 17:49:03", "expire_time": "2026-12-31 23:59:59", "target_type": 3, "update_time": "2026-10-29 17:49:03", "block_reason": "异常登录 IP，多次密码尝试失败", "create_operator": "运营后台"}]}', '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6719, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.4101, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.301, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2937, "node_id": null, "node_type": "table"}]', '查询所有黑名单用户及其加入时间', NULL, NULL, '2026-10-29 17:49:58', '2026-10-29 17:50:39');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (76, '3458b1cd-95b3-41ec-9d8c-4f599076a5b1', '查询所有黑名单用户及其加入时间', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'success', NULL, '{"row_count": 3, "truncated": false, "data_preview": [{"id": 1, "target_id": "U10004", "is_deleted": 0, "risk_level": 3, "block_scene": "全部交易", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 1, "update_time": "2026-10-29 17:49:03", "block_reason": "反洗钱监测：多笔快进快出交易，命中监管预警模型", "create_operator": "风控系统"}, {"id": 2, "target_id": "6222020000001002", "is_deleted": 0, "risk_level": 2, "block_scene": "提现", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 2, "update_time": "2026-10-29 17:49:03", "block_reason": "疑似套现：同一商户高频大额提现", "create_operator": "风控系统"}, {"id": 3, "target_id": "203.0.113.66", "is_deleted": 0, "risk_level": 1, "block_scene": "转账", "create_time": "2026-10-29 17:49:03", "expire_time": "2026-12-31 23:59:59", "target_type": 3, "update_time": "2026-10-29 17:49:03", "block_reason": "异常登录 IP，多次密码尝试失败", "create_operator": "运营后台"}]}', '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6719, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.4101, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.301, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2937, "node_id": null, "node_type": "table"}]', '查询所有黑名单用户及其加入时间', NULL, NULL, '2026-10-29 19:08:01', '2026-10-29 19:08:21');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (77, '3458b1cd-95b3-41ec-9d8c-4f599076a5b1', '查询所有黑名单用户及其加入时间', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'pending', NULL, NULL, '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6719, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.4101, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.301, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2937, "node_id": null, "node_type": "table"}]', '查询所有黑名单用户及其加入时间', NULL, NULL, '2026-10-29 19:11:53', '2026-10-29 19:11:53');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (78, 'debug-session-1', '查询所有黑名单用户及其加入时间', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'success', NULL, '{"row_count": 3, "truncated": false, "data_preview": [{"id": 1, "target_id": "U10004", "is_deleted": 0, "risk_level": 3, "block_scene": "全部交易", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 1, "update_time": "2026-10-29 17:49:03", "block_reason": "反洗钱监测：多笔快进快出交易，命中监管预警模型", "create_operator": "风控系统"}, {"id": 2, "target_id": "6222020000001002", "is_deleted": 0, "risk_level": 2, "block_scene": "提现", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 2, "update_time": "2026-10-29 17:49:03", "block_reason": "疑似套现：同一商户高频大额提现", "create_operator": "风控系统"}, {"id": 3, "target_id": "203.0.113.66", "is_deleted": 0, "risk_level": 1, "block_scene": "转账", "create_time": "2026-10-29 17:49:03", "expire_time": "2026-12-31 23:59:59", "target_type": 3, "update_time": "2026-10-29 17:49:03", "block_reason": "异常登录 IP，多次密码尝试失败", "create_operator": "运营后台"}]}', '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6719, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.4101, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.301, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2937, "node_id": null, "node_type": "table"}]', '查询所有黑名单用户及其加入时间', NULL, NULL, '2026-10-29 19:12:15', '2026-10-29 19:12:15');
INSERT INTO sql_generation_history (id, session_id, user_query, generated_sql, sql_dialect, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, governance_validated, validation_status, validation_error, execution_status, execution_error, execution_result, matched_knowledge, retrieval_query, feedback_score, feedback_comment, created_at, updated_at) VALUES (79, 'b2e6a86e-26ba-475c-bf9f-5e95d6dfd144', '查询所有黑名单用户及其加入时间', 'SELECT * FROM risk_blacklist', 'mysql', NULL, NULL, NULL, NULL, 0, 'success', NULL, 'success', NULL, '{"row_count": 3, "truncated": false, "data_preview": [{"id": 1, "target_id": "U10004", "is_deleted": 0, "risk_level": 3, "block_scene": "全部交易", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 1, "update_time": "2026-10-29 17:49:03", "block_reason": "反洗钱监测：多笔快进快出交易，命中监管预警模型", "create_operator": "风控系统"}, {"id": 2, "target_id": "6222020000001002", "is_deleted": 0, "risk_level": 2, "block_scene": "提现", "create_time": "2026-10-29 17:49:03", "expire_time": null, "target_type": 2, "update_time": "2026-10-29 17:49:03", "block_reason": "疑似套现：同一商户高频大额提现", "create_operator": "风控系统"}, {"id": 3, "target_id": "203.0.113.66", "is_deleted": 0, "risk_level": 1, "block_scene": "转账", "create_time": "2026-10-29 17:49:03", "expire_time": "2026-12-31 23:59:59", "target_type": 3, "update_time": "2026-10-29 17:49:03", "block_reason": "异常登录 IP，多次密码尝试失败", "create_operator": "运营后台"}]}', '[{"name": "risk_blacklist", "score": 1.0, "node_id": null, "node_type": "table"}, {"name": "user_account", "score": 0.6719, "node_id": null, "node_type": "table"}, {"name": "account_freeze_log", "score": 0.4101, "node_id": null, "node_type": "table"}, {"name": "daily_account_check", "score": 0.301, "node_id": null, "node_type": "table"}, {"name": "users", "score": 0.2937, "node_id": null, "node_type": "table"}]', '查询所有黑名单用户及其加入时间', NULL, NULL, '2026-10-29 19:15:23', '2026-10-29 19:16:00');

-- ------------------------------------------------------------
-- user_feedback — 用户反馈表（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL,
    feedback_content TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (history_id) REFERENCES sql_generation_history (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS user_feedback_idx_history_id ON user_feedback (history_id);

-- ------------------------------------------------------------
-- table_schema — 数据表信息表（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS table_schema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    table_comment TEXT,
    properties TEXT,
    database_name TEXT DEFAULT 'text2sql_db',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_table_name UNIQUE (table_name, database_name)
);

-- ------------------------------------------------------------
-- column_schema — 字段信息表（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS column_schema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT NOT NULL,
    is_nullable INTEGER DEFAULT 1,
    is_primary_key INTEGER DEFAULT 0,
    column_comment TEXT,
    default_value TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS column_schema_idx_table_id ON column_schema (table_id);

-- ------------------------------------------------------------
-- knowledge_metadata — 知识库元数据表（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    node_label TEXT NOT NULL,
    description TEXT,
    properties TEXT,
    related_tables TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_node_label ON knowledge_metadata (node_label);
CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_node_type ON knowledge_metadata (node_type);
CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_related_tables ON knowledge_metadata (related_tables);

-- ------------------------------------------------------------
-- retrieval_terms — 检索词表（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retrieval_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    node_id TEXT NOT NULL,
    term_type TEXT,
    weight REAL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS retrieval_terms_idx_node_id ON retrieval_terms (node_id);
CREATE INDEX IF NOT EXISTS retrieval_terms_idx_term ON retrieval_terms (term);
