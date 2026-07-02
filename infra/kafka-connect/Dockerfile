FROM confluentinc/cp-kafka-connect:7.6.0

USER root

RUN confluent-hub install --no-prompt confluentinc/kafka-connect-jdbc:10.7.4 && \
    confluent-hub install --no-prompt confluentinc/kafka-connect-elasticsearch:14.1.0

# PostgreSQL JDBC driver for JdbcSinkConnector (ADD avoids yum/curl in UBI base)
ADD https://jdbc.postgresql.org/download/postgresql-42.7.3.jar \
    /usr/share/confluent-hub-components/confluentinc-kafka-connect-jdbc/lib/postgresql-42.7.3.jar

USER appuser
