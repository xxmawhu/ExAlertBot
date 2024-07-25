cd $(dirname ${BASH_SOURCE[0]})
rsync -avz --exclude='deploy.sh' *.sh /trader/ExAlertBot/
rsync -avz *.py /trader/ExAlertBot/
