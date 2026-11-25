-- Rossmann Store Sales - relational schema (SQLite dialect)
-- The schema is intentionally simple (star-like): one fact table with
-- store-day transactions and one dimension table with static store attributes.

DROP TABLE IF EXISTS train_sales;
DROP TABLE IF EXISTS test_sales;
DROP TABLE IF EXISTS stores;

CREATE TABLE stores (
    Store                     INTEGER PRIMARY KEY,
    StoreType                 TEXT    NOT NULL,
    Assortment                TEXT    NOT NULL,
    CompetitionDistance       REAL,
    CompetitionOpenSinceMonth INTEGER,
    CompetitionOpenSinceYear  INTEGER,
    Promo2                    INTEGER NOT NULL CHECK (Promo2 IN (0, 1)),
    Promo2SinceWeek           INTEGER,
    Promo2SinceYear           INTEGER,
    PromoInterval             TEXT
);

CREATE TABLE train_sales (
    Store         INTEGER NOT NULL,
    Date          TEXT    NOT NULL,          -- ISO-8601 (YYYY-MM-DD)
    DayOfWeek     INTEGER NOT NULL CHECK (DayOfWeek BETWEEN 1 AND 7),
    Sales         INTEGER NOT NULL CHECK (Sales >= 0),
    Customers     INTEGER NOT NULL CHECK (Customers >= 0),
    Open          INTEGER NOT NULL CHECK (Open IN (0, 1)),
    Promo         INTEGER NOT NULL CHECK (Promo IN (0, 1)),
    StateHoliday  TEXT    NOT NULL,          -- 0, a, b, c
    SchoolHoliday INTEGER NOT NULL CHECK (SchoolHoliday IN (0, 1)),
    PRIMARY KEY (Store, Date),
    FOREIGN KEY (Store) REFERENCES stores (Store)
);

CREATE TABLE test_sales (
    Id            INTEGER PRIMARY KEY,
    Store         INTEGER NOT NULL,
    Date          TEXT    NOT NULL,
    DayOfWeek     INTEGER NOT NULL,
    Open          INTEGER,
    Promo         INTEGER NOT NULL,
    StateHoliday  TEXT    NOT NULL,
    SchoolHoliday INTEGER NOT NULL,
    FOREIGN KEY (Store) REFERENCES stores (Store)
);

CREATE INDEX idx_train_date ON train_sales (Date);
CREATE INDEX idx_train_store ON train_sales (Store);
CREATE INDEX idx_train_promo ON train_sales (Promo);
CREATE INDEX idx_test_store_date ON test_sales (Store, Date);
