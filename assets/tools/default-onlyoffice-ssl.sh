#!/bin/bash

if [ ! -f /var/www/onlyoffice/Data/certs/dhparam.pem ]; then
        sudo openssl dhparam -out dhparam.pem 2048

        mv dhparam.pem /var/www/onlyoffice/Data/certs/dhparam.pem;
fi

DOCKER_ONLYOFFICE_SUBNET=$(ip -o -f inet addr show | awk '/scope global/ {print $4}');

cp /app/onlyoffice/config/nginx/onlyoffice-ssl default-onlyoffice-ssl.conf;

sed 's,{{SSL_CERTIFICATE_PATH}},/var/www/onlyoffice/Data/certs/onlyoffice.crt,' -i default-onlyoffice-ssl.conf;
sed 's,{{SSL_KEY_PATH}},/var/www/onlyoffice/Data/certs/onlyoffice.key,' -i default-onlyoffice-ssl.conf;
sed 's,{{SSL_DHPARAM_PATH}},/var/www/onlyoffice/Data/certs/dhparam.pem,' -i default-onlyoffice-ssl.conf;
sed 's,{{SSL_VERIFY_CLIENT}},off,' -i default-onlyoffice-ssl.conf;
sed '/{{CA_CERTIFICATES_PATH}}/d' -i default-onlyoffice-ssl.conf;
sed 's/{{ONLYOFFICE_HTTPS_HSTS_MAXAGE}}/63072000/' -i default-onlyoffice-ssl.conf;
sed 's,{{DOCKER_ONLYOFFICE_SUBNET}},'"${DOCKER_ONLYOFFICE_SUBNET}"',' -i default-onlyoffice-ssl.conf;
sed 's/{{ONLYOFFICE_NIGNX_KEEPLIVE}}/64/g' -i default-onlyoffice-ssl.conf;

SSL_OCSP_CERTIFICATE_PATH="/var/www/onlyoffice/Data/certs/stapling.trusted.crt"

# if dhparam path is valid, add to the config, otherwise remove the option
if [ -r "${SSL_OCSP_CERTIFICATE_PATH}" ]; then
        sed 's,{{SSL_OCSP_CERTIFICATE_PATH}},'"${SSL_OCSP_CERTIFICATE_PATH}"',' -i default-onlyoffice-ssl.conf;
else
        sed '/ssl_stapling/d' -i default-onlyoffice-ssl.conf;
        sed '/ssl_stapling_verify/d' -i default-onlyoffice-ssl.conf;
        sed '/ssl_trusted_certificate/d' -i default-onlyoffice-ssl.conf;
        sed '/resolver/d' -i default-onlyoffice-ssl.conf;
        sed '/resolver_timeout/d' -i default-onlyoffice-ssl.conf;
fi

sed '/mail\.default-api-scheme/s/\(value\s*=\s*\"\).*\"/\1https\"/' -i /var/www/onlyoffice/Services/MailAggregator/ASC.Mail.Aggregator.CollectionService.exe.config;

mv default-onlyoffice-ssl.conf /etc/nginx/sites-enabled/onlyoffice

service onlyofficeMailAggregator restart
service nginx reload
