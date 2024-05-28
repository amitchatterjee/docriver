CREATE USER 'keycloak'@'%' IDENTIFIED BY 'keycloak';
CREATE DATABASE keycloak CHARACTER SET utf8 COLLATE utf8_unicode_ci;
GRANT ALL PRIVILEGES ON keycloak.* TO 'keycloak'@'%';
FLUSH PRIVILEGES;