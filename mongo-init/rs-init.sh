#replicaset local
# Attendre que MongoDB soit prêt
echo "⏳ Attente que MongoDB soit prêt..."
until mongosh -u root -p root --authenticationDatabase admin --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
  sleep 2
done
echo "✅ MongoDB est prêt."

# Initialiser le replica set
echo "⚡ Initialisation du replica set..."
mongosh -u root -p root --authenticationDatabase admin <<EOF
rs.initiate()
rs.status()
EOF
echo "✅ Replica set initialisé."
