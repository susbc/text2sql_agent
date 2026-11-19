-- ============================================================
-- seed_business.sql — 业务表种子（8 表，30 行）
-- 源：MySQL business_db（只读迁移）。
-- 由 scripts/migrate_mysql_to_sqlite.py 生成；请勿手工编辑，重跑脚本可再生成。
-- 类型映射（spec §5.1）：INTEGER/TEXT/NUMERIC/REAL；去 COLLATE/ENGINE/COMMENT。
-- ============================================================


-- ------------------------------------------------------------
-- account_freeze_log — 账户资金冻结解冻日志（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS account_freeze_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    freeze_no TEXT NOT NULL,
    account_no TEXT NOT NULL,
    freeze_amount NUMERIC NOT NULL,
    freeze_type INTEGER NOT NULL,
    freeze_status INTEGER NOT NULL DEFAULT 1,
    operate_user TEXT NOT NULL,
    reason TEXT NOT NULL,
    expire_time TEXT,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uk_freeze_no UNIQUE (freeze_no)
);
CREATE INDEX IF NOT EXISTS idx_account_no ON account_freeze_log (account_no);
CREATE INDEX IF NOT EXISTS idx_freeze_status ON account_freeze_log (freeze_status);

-- ------------------------------------------------------------
-- daily_account_check — 日终渠道资金对账表（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_account_check (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_date TEXT NOT NULL,
    channel_code TEXT NOT NULL,
    platform_total_income NUMERIC NOT NULL DEFAULT 0.0000,
    platform_total_out NUMERIC NOT NULL DEFAULT 0.0000,
    channel_total_income NUMERIC NOT NULL DEFAULT 0.0000,
    channel_total_out NUMERIC NOT NULL DEFAULT 0.0000,
    diff_amount NUMERIC NOT NULL DEFAULT 0.0000,
    check_status INTEGER NOT NULL DEFAULT 0,
    handle_operator TEXT,
    handle_remark TEXT,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uk_date_channel UNIQUE (check_date, channel_code)
);
CREATE INDEX IF NOT EXISTS idx_check_status ON daily_account_check (check_status);

-- ------------------------------------------------------------
-- fee_rate_config — 金融手续费费率配置表（0 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fee_rate_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_code TEXT NOT NULL,
    trans_scene INTEGER NOT NULL,
    fee_type INTEGER NOT NULL,
    fixed_fee NUMERIC NOT NULL DEFAULT 0.0000,
    rate_fee NUMERIC NOT NULL DEFAULT 0.000000,
    min_fee NUMERIC NOT NULL DEFAULT 0.0000,
    max_fee NUMERIC NOT NULL DEFAULT 999999.9999,
    user_level INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    effective_start TEXT NOT NULL,
    effective_end TEXT,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uk_config_code UNIQUE (config_code)
);
CREATE INDEX IF NOT EXISTS idx_trans_scene ON fee_rate_config (trans_scene);

-- ------------------------------------------------------------
-- prediction_results（1 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prediction_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exported_at TEXT NOT NULL,
    model_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    features_json TEXT NOT NULL,
    prediction TEXT NOT NULL,
    encoded_prediction REAL,
    probability REAL,
    diagnostics_json TEXT
);
INSERT INTO prediction_results (id, exported_at, model_id, row_index, features_json, prediction, encoded_prediction, probability, diagnostics_json) VALUES (1, '2026-11-12 19:44:39', 'automl:automl_68287661d7da4016a7fb50fea7689802', 0, '{"age": 35, "order_fee": 128.5, "city_code": "北京"}', 'no', 0.0, 0.979167, '{"unknown_input_keys": ["order_fee", "city_code"], "missing_columns_imputed": ["job", "marital", "education", "default", "housing", "loan", "contact", "month", "day_of_week", "duration", "campaign", "pdays", "previous", "poutcome", "emp_var_rate", "cons_price_index", "cons_conf_index", "lending_rate3m", "nr_employed"]}');

-- ------------------------------------------------------------
-- risk_blacklist — 风控黑名单管控表（3 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT NOT NULL,
    target_type INTEGER NOT NULL,
    risk_level INTEGER NOT NULL,
    block_scene TEXT NOT NULL,
    block_reason TEXT NOT NULL,
    expire_time TEXT,
    create_operator TEXT NOT NULL,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uk_target_type_id UNIQUE (target_id, target_type)
);
CREATE INDEX IF NOT EXISTS idx_risk_level ON risk_blacklist (risk_level);
INSERT INTO risk_blacklist (id, target_id, target_type, risk_level, block_scene, block_reason, expire_time, create_operator, create_time, update_time, is_deleted) VALUES (1, 'U10004', 1, 3, '全部交易', '反洗钱监测：多笔快进快出交易，命中监管预警模型', NULL, '风控系统', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO risk_blacklist (id, target_id, target_type, risk_level, block_scene, block_reason, expire_time, create_operator, create_time, update_time, is_deleted) VALUES (2, '6222020000001002', 2, 2, '提现', '疑似套现：同一商户高频大额提现', NULL, '风控系统', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO risk_blacklist (id, target_id, target_type, risk_level, block_scene, block_reason, expire_time, create_operator, create_time, update_time, is_deleted) VALUES (3, '203.0.113.66', 3, 1, '转账', '异常登录 IP，多次密码尝试失败', '2026-12-31 23:59:59', '运营后台', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);

-- ------------------------------------------------------------
-- transaction_record — 全量交易流水表（8 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transaction_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trans_no TEXT NOT NULL,
    out_trans_no TEXT,
    account_no TEXT NOT NULL,
    opposite_account_no TEXT,
    trans_type INTEGER NOT NULL,
    trans_amount NUMERIC NOT NULL,
    fee_amount NUMERIC NOT NULL DEFAULT 0.0000,
    actual_amount NUMERIC NOT NULL,
    balance_after NUMERIC NOT NULL,
    trans_status INTEGER NOT NULL,
    pay_channel TEXT NOT NULL,
    currency_code TEXT NOT NULL DEFAULT 'CNY',
    order_batch_no TEXT,
    risk_verify_result INTEGER NOT NULL DEFAULT 1,
    trans_desc TEXT NOT NULL,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uk_trans_no UNIQUE (trans_no)
);
CREATE INDEX IF NOT EXISTS idx_account_no ON transaction_record (account_no);
CREATE INDEX IF NOT EXISTS idx_create_time ON transaction_record (create_time);
CREATE INDEX IF NOT EXISTS idx_order_batch_no ON transaction_record (order_batch_no);
CREATE INDEX IF NOT EXISTS idx_trans_status ON transaction_record (trans_status);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (1, 'T202610200001', NULL, '6222020000001001', NULL, 1, 5000.0000, 0.0000, 5000.0000, 30800.5000, 2, 'alipay', 'CNY', NULL, 1, '充值', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (2, 'T202610200002', NULL, '6222020000001001', '6222020000001005', 3, 1200.0000, 1.2000, 1198.8000, 29601.7000, 2, 'alipay', 'CNY', NULL, 1, '转账支出', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (3, 'T202610210003', NULL, '6222020000001003', NULL, 2, 80000.0000, 80.0000, 79920.0000, 899920.0000, 2, 'unionpay', 'CNY', NULL, 1, '提现', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (4, 'T202610210004', 'B20261021A', '6222020000001004', NULL, 1, 2000.0000, 0.0000, 2000.0000, 0.0000, 3, 'wechat', 'CNY', NULL, 1, '充值失败退款中', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (5, 'T202610220005', NULL, '6222020000001002', NULL, 7, 200.0000, 0.0000, 200.0000, 320.0000, 2, 'alipay', 'CNY', NULL, 1, '红包发放', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (6, 'T202610220006', NULL, '6222020000001006', NULL, 1, 3000.0000, 0.0000, 3000.0000, 11999.9900, 2, 'unionpay', 'CNY', NULL, 1, '充值', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (7, 'T202610230007', NULL, '6222020000001005', '6222020000001002', 4, 800.0000, 0.8000, 799.2000, 2760.7500, 2, 'alipay', 'CNY', NULL, 1, '转账收入', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);
INSERT INTO transaction_record (id, trans_no, out_trans_no, account_no, opposite_account_no, trans_type, trans_amount, fee_amount, actual_amount, balance_after, trans_status, pay_channel, currency_code, order_batch_no, risk_verify_result, trans_desc, create_time, update_time, is_deleted) VALUES (8, 'T202610240008', NULL, '6222020000001001', NULL, 2, 1000.0000, 5.0000, 995.0000, 28606.7000, 2, 'unionpay', 'CNY', NULL, 1, '提现', '2026-10-29 17:49:03', '2026-10-29 17:49:03', 0);

-- ------------------------------------------------------------
-- user_account — 用户资金主账户表（6 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    account_no TEXT NOT NULL,
    account_type INTEGER NOT NULL DEFAULT 1,
    balance NUMERIC NOT NULL DEFAULT 0.0000,
    frozen_balance NUMERIC NOT NULL DEFAULT 0.0000,
    total_income NUMERIC NOT NULL DEFAULT 0.0000,
    total_expense NUMERIC NOT NULL DEFAULT 0.0000,
    currency_code TEXT NOT NULL DEFAULT 'CNY',
    account_status INTEGER NOT NULL DEFAULT 1,
    risk_level INTEGER NOT NULL DEFAULT 1,
    open_channel TEXT NOT NULL,
    remark TEXT,
    create_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uk_account_no UNIQUE (account_no),
    CONSTRAINT uk_user_id UNIQUE (user_id)
);
CREATE INDEX IF NOT EXISTS idx_account_status ON user_account (account_status);
CREATE INDEX IF NOT EXISTS idx_risk_level ON user_account (risk_level);
INSERT INTO user_account (id, user_id, account_no, account_type, balance, frozen_balance, total_income, total_expense, currency_code, account_status, risk_level, open_channel, remark, create_time, update_time, is_deleted) VALUES (1, 'U10001', '6222020000001001', 1, 25800.5000, 0.0000, 0.0000, 0.0000, 'CNY', 1, 1, 'APP', '正常商户用户', '2026-10-29 17:48:16', '2026-10-29 17:48:16', 0);
INSERT INTO user_account (id, user_id, account_no, account_type, balance, frozen_balance, total_income, total_expense, currency_code, account_status, risk_level, open_channel, remark, create_time, update_time, is_deleted) VALUES (2, 'U10002', '6222020000001002', 1, 120.0000, 0.0000, 0.0000, 0.0000, 'CNY', 1, 2, 'H5', '近期提现频繁', '2026-10-29 17:48:16', '2026-10-29 17:48:16', 0);
INSERT INTO user_account (id, user_id, account_no, account_type, balance, frozen_balance, total_income, total_expense, currency_code, account_status, risk_level, open_channel, remark, create_time, update_time, is_deleted) VALUES (3, 'U10003', '6222020000001003', 2, 980000.0000, 0.0000, 0.0000, 0.0000, 'CNY', 1, 1, 'PC', '企业结算账户', '2026-10-29 17:48:16', '2026-10-29 17:48:16', 0);
INSERT INTO user_account (id, user_id, account_no, account_type, balance, frozen_balance, total_income, total_expense, currency_code, account_status, risk_level, open_channel, remark, create_time, update_time, is_deleted) VALUES (4, 'U10004', '6222020000001004', 1, 0.0000, 0.0000, 0.0000, 0.0000, 'CNY', 1, 3, 'APP', '涉嫌洗钱已冻结', '2026-10-29 17:48:16', '2026-10-29 17:48:16', 0);
INSERT INTO user_account (id, user_id, account_no, account_type, balance, frozen_balance, total_income, total_expense, currency_code, account_status, risk_level, open_channel, remark, create_time, update_time, is_deleted) VALUES (5, 'U10005', '6222020000001005', 1, 3560.7500, 0.0000, 0.0000, 0.0000, 'CNY', 1, 1, 'APP', '', '2026-10-29 17:48:16', '2026-10-29 17:48:16', 0);
INSERT INTO user_account (id, user_id, account_no, account_type, balance, frozen_balance, total_income, total_expense, currency_code, account_status, risk_level, open_channel, remark, create_time, update_time, is_deleted) VALUES (6, 'U10006', '6222020000001006', 3, 8999.9900, 0.0000, 0.0000, 0.0000, 'CNY', 1, 2, 'APP', '子账户', '2026-10-29 17:48:16', '2026-10-29 17:48:16', 0);

-- ------------------------------------------------------------
-- users（12 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER NOT NULL PRIMARY KEY,
    rfm_score REAL NOT NULL,
    orders_30d INTEGER NOT NULL,
    support_tickets INTEGER NOT NULL,
    event_date TEXT NOT NULL,
    is_churned INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_date ON users (event_date);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (1, 95.0, 10, 0, '2025-01-10', 0);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (2, 91.0, 9, 1, '2025-01-20', 0);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (3, 87.0, 8, 0, '2025-02-10', 0);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (4, 82.0, 7, 1, '2025-02-20', 0);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (5, 76.0, 6, 1, '2025-03-10', 0);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (6, 71.0, 5, 2, '2025-03-20', 0);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (7, 46.0, 3, 3, '2025-04-10', 1);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (8, 39.0, 2, 4, '2025-04-20', 1);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (9, 34.0, 2, 5, '2025-05-01', 1);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (10, 28.0, 1, 6, '2025-05-10', 1);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (11, 22.0, 1, 7, '2025-05-20', 1);
INSERT INTO users (user_id, rfm_score, orders_30d, support_tickets, event_date, is_churned) VALUES (12, 18.0, 0, 8, '2025-05-25', 1);
