-- TODO change all timestamps to TIMESTAMP(6) for milliseconds precision

CREATE DATABASE IF NOT EXISTS docriver;
-- CREATE USER 'docriver'@'%' IDENTIFIED BY 'docriver';
-- CREATE USER 'docriver'@'localhost' IDENTIFIED BY 'docriver';
-- GRANT ALL ON docriver.* TO 'docriver'@'%';
-- GRANT ALL ON docriver.* TO 'docriver'@'localhost';
-- GRANT ALL ON information_schema.* TO 'docriver'@'%';
-- GRANT ALL ON information_schema.* TO 'docriver'@'localhost';
-- GRANT SELECT ON performance_schema.* TO 'docriver'@'%';
-- GRANT SELECT ON performance_schema.* TO 'docriver'@'localhost';
-- FLUSH PRIVILEGES;

USE docriver;
CREATE TABLE IF NOT EXISTS TX (
    ID BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,

    TX VARCHAR(250) NOT NULL,
    REALM VARCHAR(50),

    CREATED_AT TIMESTAMP DEFAULT NOW(),
    UNIQUE (TX, REALM),
    KEY(REALM)
);

CREATE TABLE IF NOT EXISTS TX_EVENT (
    ID BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
    EVENT VARCHAR(50) NOT NULL,
    EVENT_TIME DATETIME NOT NULL DEFAULT NOW(),
    -- Ingested: I, Processing in progress: P, Processing completed: C, Processing failed: F, Transaction deleted: D, Transaction replaced: R,  etc.
    STATUS CHAR(1) NOT NULL,
    DESCRIPTION VARCHAR(200),

    TX_ID BIGINT UNSIGNED NOT NULL,

    CREATED_AT TIMESTAMP DEFAULT NOW(),
    KEY(EVENT_TIME),
    FOREIGN KEY (TX_ID) REFERENCES TX(ID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS DOC (
    ID BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,

    DOCUMENT VARCHAR(250) NOT NULL,
    TYPE VARCHAR(25) NOT NULL,
    MIME_TYPE VARCHAR(50),

    REPLACES_DOC_ID BIGINT UNSIGNED,

    CREATED_AT TIMESTAMP DEFAULT NOW(),
    UNIQUE (DOCUMENT),
    FOREIGN KEY (REPLACES_DOC_ID) REFERENCES DOC(ID) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS DOC_VERSION (
    ID BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,

    DOC_ID BIGINT UNSIGNED NOT NULL,
    TX_ID BIGINT UNSIGNED NULL,

    LOCATION_URL VARCHAR(250),

    CREATED_AT TIMESTAMP DEFAULT NOW(),
    UNIQUE (LOCATION_URL),
    FOREIGN KEY (TX_ID) REFERENCES TX(ID) ON DELETE SET NULL,
    FOREIGN KEY (DOC_ID) REFERENCES DOC(ID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS DOC_REF (
    ID BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
    RESOURCE_TYPE VARCHAR(50) NOT NULL,
    RESOURCE_ID VARCHAR(50) NOT NULL,
    DESCRIPTION VARCHAR(1000),

    DOC_VERSION_ID BIGINT UNSIGNED NOT NULL,

    CREATED_AT TIMESTAMP DEFAULT NOW(),
    -- UNIQUE (DOC_VERSION_ID, RESOURCE_ID),
    KEY(RESOURCE_TYPE),
    KEY(RESOURCE_ID),
    FOREIGN KEY (DOC_VERSION_ID) REFERENCES DOC_VERSION(ID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS DOC_REF_PROPERTY (
    ID BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
    KEY_NAME VARCHAR(255) NOT NULL,
    VALUE VARCHAR(1000),

    REF_ID BIGINT UNSIGNED NOT NULL,

    CREATED_AT TIMESTAMP DEFAULT NOW(),
    UNIQUE (REF_ID, KEY_NAME),
    KEY(KEY_NAME),
    FOREIGN KEY (REF_ID) REFERENCES DOC_REF(ID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS DOC_EVENT (
    ID BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
    EVENT_TIME DATETIME NOT NULL DEFAULT NOW(),
    -- Ingested: I, Referenced: J, Processing in progress: P, Processing completed: C, Processing failed: F, Document deleted: D, Document replaced: R, New version: V, etc.
    STATUS CHAR(1) NOT NULL,
    DESCRIPTION VARCHAR(200),
    -- If status = R, specify the Document that replaced it
    REF_DOC_ID BIGINT UNSIGNED NULL,
    REF_TX_ID BIGINT UNSIGNED NULL,

    DOC_ID BIGINT UNSIGNED NOT NULL,

    CREATED_AT TIMESTAMP DEFAULT NOW(),
    KEY(EVENT_TIME),
    FOREIGN KEY (DOC_ID) REFERENCES DOC(ID) ON DELETE CASCADE,
    FOREIGN KEY (REF_DOC_ID) REFERENCES DOC(ID) ON DELETE SET NULL,
    FOREIGN KEY (REF_TX_ID) REFERENCES TX(ID) ON DELETE SET NULL
);


