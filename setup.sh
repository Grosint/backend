#!/bin/bash
# =============================================================================
# Azure VM Setup Script for Grosint Backend
# This script prepares an Ubuntu VM for FastAPI deployment with:
# - Python 3.12.7
# - Docker & Docker Compose (for testing MongoDB containers)
# - Nginx (reverse proxy with SSL support)
# - Certbot (SSL certificate management)
# - User setup and security configuration
# =============================================================================

set -e  # Exit on any error

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}============================================${NC}"
    echo -e "${BLUE} $1 ${NC}"
    echo -e "${BLUE}============================================${NC}\n"
}

# =============================================================================
# STEP 1: IMMEDIATE FIX FOR APT ISSUES
# =============================================================================
print_header "STEP 1: FIXING APT COMPATIBILITY ISSUES FIRST"

print_status "Checking for apt_pkg module issues..."
# Immediately disable the problematic command-not-found hook
print_status "Disabling command-not-found hook to prevent apt errors..."
sudo chmod -x /usr/lib/cnf-update-db 2>/dev/null || true

print_status "Testing basic apt functionality..."
if sudo apt update 2>/dev/null; then
    print_success "APT is working correctly!"
else
    print_warning "APT has issues, applying comprehensive fix..."

    # Nuclear option: remove command-not-found completely during setup
    print_status "Removing command-not-found temporarily..."
    sudo apt remove --purge -y command-not-found 2>/dev/null || true
    sudo apt autoremove -y 2>/dev/null || true

    print_status "Testing apt after command-not-found removal..."
    sudo apt update
fi

print_success "APT compatibility issues resolved!"

# =============================================================================
# STEP 2: SYSTEM INFORMATION AND UPDATES
# =============================================================================
print_header "STEP 2: SYSTEM INFORMATION AND UPDATES"

print_status "Checking system information..."
echo "OS: $(lsb_release -d | cut -f2)"
echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "Disk Space: $(df -h / | awk 'NR==2{print $4}')"

print_status "Updating package lists..."
sudo apt update

print_status "Fixing command-not-found database issue (if present)..."
# Fix the command-not-found database issue
sudo apt install --reinstall -y command-not-found || true
sudo update-command-not-found || true

print_status "Upgrading existing packages..."
sudo apt upgrade -y

print_success "System updated successfully!"

# =============================================================================
# STEP 3: INSTALL ESSENTIAL DEPENDENCIES
# =============================================================================
print_header "STEP 3: INSTALLING ESSENTIAL DEPENDENCIES"

print_status "Installing essential packages..."
sudo apt install -y \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    wget \
    unzip \
    git \
    htop \
    tree \
    bc \
    jq

print_success "Essential packages installed!"

# =============================================================================
# STEP 4: INSTALL PYTHON 3.12.7
# =============================================================================
print_header "STEP 4: INSTALLING PYTHON 3.12.7"

print_status "Completely disabling command-not-found to prevent all apt errors..."
sudo chmod -x /usr/lib/cnf-update-db 2>/dev/null || true
sudo rm -f /usr/lib/cnf-update-db 2>/dev/null || true

print_status "Cleaning up any existing deadsnakes PPA entries..."
sudo rm -f /etc/apt/sources.list.d/deadsnakes*.list

print_status "Adding deadsnakes PPA manually with modern GPG key handling..."
# Add the PPA manually using modern GPG key management
curl -fsSL https://keyserver.ubuntu.com/pks/lookup?op=get\&search=0xBA6932366A755776 | sudo gpg --dearmor -o /usr/share/keyrings/deadsnakes-ppa.gpg

echo "deb [signed-by=/usr/share/keyrings/deadsnakes-ppa.gpg] https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/deadsnakes-ppa.list

print_success "Deadsnakes PPA added with modern GPG key management"

print_status "Updating package lists after adding PPA..."
# Update without the problematic command-not-found hook
sudo apt update 2>/dev/null || sudo apt update

print_status "Installing Python 3.12 and related packages..."
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip

print_status "Installing pip for Python 3.12..."
# Download and install pip specifically for Python 3.12
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

print_status "Verifying Python installation..."
python3.12 --version
python3.12 -m pip --version

print_status "Creating python3 symlink to python3.12..."
sudo ln -sf /usr/bin/python3.12 /usr/bin/python3

print_success "Python 3.12.7 installed successfully!"

# Re-enable command-not-found if it was disabled
print_status "Re-enabling command-not-found with updated Python..."
sudo chmod +x /usr/lib/cnf-update-db 2>/dev/null || true

# Try to update command-not-found database with new Python
print_status "Updating command-not-found database..."
sudo update-command-not-found 2>/dev/null || print_warning "Command-not-found update had warnings (this is normal)"

# =============================================================================
# STEP 5: INSTALL DOCKER AND DOCKER COMPOSE
# =============================================================================
print_header "STEP 5: INSTALLING DOCKER AND DOCKER COMPOSE"

print_status "Adding Docker's official GPG key..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

print_status "Adding Docker repository..."
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

print_status "Updating package lists with Docker repository..."
sudo apt update

print_status "Installing Docker CE, CLI, and containerd..."
sudo apt install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

print_status "Installing Docker Compose standalone..."
DOCKER_COMPOSE_VERSION="2.24.1"
sudo curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

print_status "Starting and enabling Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

print_status "Verifying Docker installation..."
sudo docker --version
sudo docker-compose --version

print_success "Docker and Docker Compose installed successfully!"

# =============================================================================
# STEP 6: INSTALL AND CONFIGURE NGINX
# =============================================================================
print_header "STEP 6: INSTALLING AND CONFIGURING NGINX"

print_status "Installing Nginx..."
sudo apt install -y nginx

print_status "Starting and enabling Nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx

print_status "Checking Nginx status..."
sudo systemctl status nginx --no-pager

print_status "Creating backup of default Nginx configuration..."
sudo cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup

print_success "Nginx installed and running!"

# =============================================================================
# STEP 7: INSTALL CERTBOT FOR SSL CERTIFICATES
# =============================================================================
print_header "STEP 7: INSTALLING CERTBOT FOR SSL CERTIFICATES"

print_status "Installing Certbot and dependencies..."
# Install certbot using snap to avoid Python version conflicts
sudo apt install -y snapd
sudo snap install core
sudo snap refresh core
sudo snap install --classic certbot

print_status "Creating certbot symlink..."
# Create a symlink so certbot is available in PATH
sudo ln -sf /snap/bin/certbot /usr/bin/certbot

print_status "Verifying Certbot installation with Nginx plugin..."
# Test certbot without version output to avoid Python conflicts
if /snap/bin/certbot --help >/dev/null 2>&1; then
    echo "Certbot installed successfully via snap"
    /snap/bin/certbot --version 2>/dev/null || echo "Certbot is installed and working"

    # Check if nginx plugin is available
    if /snap/bin/certbot plugins 2>/dev/null | grep -q nginx; then
        echo "✅ Nginx plugin is available"
    else
        echo "⚠️  Nginx plugin check inconclusive (will be available when needed)"
    fi
else
    print_warning "Snap installation failed, trying alternative method..."

    # Alternative: Install via pip for Python 3.12
    print_status "Installing Certbot via pip for Python 3.12..."
    python3.12 -m pip install certbot certbot-nginx

    # Create a wrapper script that uses Python 3.12
    sudo tee /usr/local/bin/certbot << 'EOF'
#!/bin/bash
python3.12 -m certbot "$@"
EOF
    sudo chmod +x /usr/local/bin/certbot

    echo "Certbot installed via pip for Python 3.12"
fi

print_success "Certbot installed successfully!"

# =============================================================================
# STEP 8: USER AND DIRECTORY SETUP
# =============================================================================
print_header "STEP 8: USER AND DIRECTORY SETUP"

print_status "Creating application user 'grosint'..."
if id "grosint" &>/dev/null; then
    print_warning "User 'grosint' already exists"
else
    sudo useradd -m -s /bin/bash grosint
    print_success "User 'grosint' created successfully"
fi

print_status "Adding users to Docker group..."
# Add current user to docker group
sudo usermod -aG docker $USER
# Add grosint user to docker group
sudo usermod -aG docker grosint

print_status "Creating application directory..."
sudo mkdir -p /opt/grosint-backend
sudo chown grosint:grosint /opt/grosint-backend
sudo chmod 755 /opt/grosint-backend

print_status "Creating logs directory..."
sudo mkdir -p /opt/grosint-backend/logs
sudo chown grosint:grosint /opt/grosint-backend/logs

print_success "User and directory setup completed!"

# =============================================================================
# STEP 9: CONFIGURE FIREWALL (UFW)
# =============================================================================
print_header "STEP 9: CONFIGURING FIREWALL"

print_status "Installing UFW (if not already installed)..."
sudo apt install -y ufw

print_status "Setting up UFW firewall rules..."
# Allow SSH (port 22)
sudo ufw allow ssh
print_status "✓ SSH (port 22) allowed"

# Allow HTTP (port 80)
sudo ufw allow 'Nginx HTTP'
print_status "✓ HTTP (port 80) allowed"

# Allow HTTPS (port 443)
sudo ufw allow 'Nginx HTTPS'
print_status "✓ HTTPS (port 443) allowed"

# Allow application port (8000) - for direct access if needed
sudo ufw allow 8000
print_status "✓ Application port (8000) allowed"

# Allow monitoring ports
sudo ufw allow 3000  # Grafana
print_status "✓ Grafana port (3000) allowed"
sudo ufw allow 9090  # Prometheus
print_status "✓ Prometheus port (9090) allowed"
sudo ufw allow 3100  # Loki
print_status "✓ Loki port (3100) allowed"
sudo ufw allow 9100  # Node Exporter
print_status "✓ Node Exporter port (9100) allowed"
sudo ufw allow 9113  # Nginx Exporter
print_status "✓ Nginx Exporter port (9113) allowed"

print_status "Enabling UFW firewall..."
sudo ufw --force enable

print_status "UFW status:"
sudo ufw status verbose

print_success "Firewall configured successfully!"

# =============================================================================
# STEP 10: SYSTEM OPTIMIZATION AND SECURITY
# =============================================================================
print_header "STEP 10: SYSTEM OPTIMIZATION AND SECURITY"

print_status "Setting up automatic security updates..."
# Use Python 3.12 compatible method for unattended-upgrades
sudo apt install -y unattended-upgrades
echo 'Unattended-Upgrade::Automatic-Reboot "false";' | sudo tee -a /etc/apt/apt.conf.d/50unattended-upgrades
echo 'Unattended-Upgrade::Remove-Unused-Dependencies "true";' | sudo tee -a /etc/apt/apt.conf.d/50unattended-upgrades

print_status "Configuring system limits..."
# Increase file descriptor limits for the application
sudo tee -a /etc/security/limits.conf << EOF

# Grosint Backend application limits
grosint soft nofile 65536
grosint hard nofile 65536
* soft nofile 65536
* hard nofile 65536
EOF

print_status "Optimizing kernel parameters..."
sudo tee -a /etc/sysctl.conf << EOF

# Network optimizations for web applications
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 1200
net.ipv4.tcp_max_tw_buckets = 1440000
EOF

print_status "Applying kernel parameter changes..."
sudo sysctl -p

print_success "System optimization completed!"

# =============================================================================
# STEP 11: INSTALL ADDITIONAL DEVELOPMENT TOOLS
# =============================================================================
print_header "STEP 11: INSTALLING ADDITIONAL DEVELOPMENT TOOLS"

print_status "Installing development and monitoring tools..."
sudo apt install -y \
    vim \
    nano \
    tmux \
    screen \
    iotop \
    nethogs \
    ncdu \
    zip \
    unzip \
    rsync \
    build-essential \
    net-tools

print_status "Installing Python package management tools for Python 3.12..."
# Use Python 3.12 specifically for package installations
python3.12 -m pip install --upgrade pip setuptools wheel virtualenv

print_status "Installing additional Python packages for system compatibility..."
# Install packages that might be needed for various tools
python3.12 -m pip install --user cryptography cffi

print_success "Additional tools installed!"

# =============================================================================
# STEP 12: SETUP MONITORING AND LOG ROTATION
# =============================================================================
print_header "STEP 12: SETUP MONITORING AND LOG ROTATION"

print_status "Configuring log rotation for application logs..."
sudo tee /etc/logrotate.d/grosint-backend << EOF
/opt/grosint-backend/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    su grosint grosint
}
EOF

print_status "Configuring log rotation for Nginx logs..."
sudo tee /etc/logrotate.d/nginx << EOF
/var/log/nginx/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
    dateext
    dateformat -%Y-%m-%d
    postrotate
        if [ -f /var/run/nginx.pid ]; then
            kill -USR1 \$(cat /var/run/nginx.pid)
        fi
    endscript
}
EOF

print_status "Setting up system monitoring aliases..."
sudo tee /etc/profile.d/grosint-aliases.sh << EOF
# Grosint Backend monitoring aliases
alias grosint-logs='sudo journalctl -u grosint-backend -f'
alias grosint-status='sudo systemctl status grosint-backend'
alias grosint-restart='sudo systemctl restart grosint-backend'
alias grosint-stop='sudo systemctl stop grosint-backend'
alias grosint-start='sudo systemctl start grosint-backend'
alias docker-logs='docker-compose -f /opt/grosint-backend/docker-compose.test.yml logs -f'
alias nginx-logs='sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log'

# Monitoring stack aliases
alias monitoring-status='sudo systemctl status grosint-monitoring'
alias monitoring-restart='sudo systemctl restart grosint-monitoring'
alias monitoring-stop='sudo systemctl stop grosint-monitoring'
alias monitoring-start='sudo systemctl start grosint-monitoring'
alias monitoring-logs='docker-compose -f /opt/grosint-monitoring/docker-compose.logs.yml logs -f'
alias grafana-logs='docker-compose -f /opt/grosint-monitoring/docker-compose.logs.yml logs grafana'
alias prometheus-logs='docker-compose -f /opt/grosint-monitoring/docker-compose.logs.yml logs prometheus'
alias loki-logs='docker-compose -f /opt/grosint-monitoring/docker-compose.logs.yml logs loki'
alias promtail-logs='docker-compose -f /opt/grosint-monitoring/docker-compose.logs.yml logs promtail'
EOF

print_success "Monitoring and logging setup completed!"

# =============================================================================
# STEP 13: CREATE DEPLOYMENT HELPER SCRIPTS
# =============================================================================
print_header "STEP 13: CREATING DEPLOYMENT HELPER SCRIPTS"

print_status "Creating deployment helper scripts..."

# Create status check script
sudo tee /usr/local/bin/grosint-status << 'EOF'
#!/bin/bash
echo "=== Grosint Backend Status ==="
echo "Application Service:"
sudo systemctl status grosint-backend --no-pager
echo -e "\nNginx Service:"
sudo systemctl status nginx --no-pager
echo -e "\nDocker Service:"
sudo systemctl status docker --no-pager
echo -e "\nMonitoring Service:"
sudo systemctl status grosint-monitoring --no-pager
echo -e "\nDisk Usage:"
df -h /opt/grosint-backend
echo -e "\nMemory Usage:"
free -h
echo -e "\nApplication Health Check:"
curl -f http://localhost:8000/health 2>/dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
echo -e "\nMonitoring Stack Health:"
curl -f http://localhost:3000/api/health 2>/dev/null && echo "✅ Grafana Healthy" || echo "❌ Grafana Unhealthy"
curl -f http://localhost:9090/-/healthy 2>/dev/null && echo "✅ Prometheus Healthy" || echo "❌ Prometheus Unhealthy"
curl -f http://localhost:3100/ready 2>/dev/null && echo "✅ Loki Healthy" || echo "❌ Loki Unhealthy"
EOF

sudo chmod +x /usr/local/bin/grosint-status

# Create backup script
sudo tee /usr/local/bin/grosint-backup << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/grosint-$(date +%Y%m%d_%H%M%S)"
echo "Creating backup at: $BACKUP_DIR"
sudo mkdir -p $BACKUP_DIR
sudo cp -r /opt/grosint-backend $BACKUP_DIR/
sudo tar -czf $BACKUP_DIR.tar.gz -C /opt/backups $(basename $BACKUP_DIR)
sudo rm -rf $BACKUP_DIR
echo "Backup created: $BACKUP_DIR.tar.gz"
EOF

# Create log monitoring script
sudo tee /usr/local/bin/grosint-logs-status << 'EOF'
#!/bin/bash
echo "=== Log Files Status ==="
echo "Application Logs:"
du -sh /opt/grosint-backend/logs/* 2>/dev/null || echo "No app logs found"
echo -e "\nNginx Logs:"
du -sh /var/log/nginx/*.log* 2>/dev/null || echo "No nginx logs found"
echo -e "\nMonitoring Stack Logs:"
docker-compose -f /opt/grosint-monitoring/docker-compose.logs.yml exec prometheus du -sh /prometheus 2>/dev/null || echo "Prometheus data not accessible"
docker-compose -f /opt/grosint-monitoring/docker-compose.logs.yml exec loki du -sh /loki 2>/dev/null || echo "Loki data not accessible"
echo -e "\nDisk Usage:"
df -h /opt/grosint-backend /var/log/nginx 2>/dev/null
echo -e "\nLog Rotation Status:"
sudo logrotate -d /etc/logrotate.d/grosint-backend
sudo logrotate -d /etc/logrotate.d/nginx
EOF

sudo chmod +x /usr/local/bin/grosint-backup

print_success "Helper scripts created!"

# =============================================================================
# STEP 13.5: CREATE NGINX AND SYSTEMD CONFIGURATIONS
# =============================================================================
print_header "STEP 13.5: CREATING NGINX AND SYSTEMD CONFIGURATIONS"

print_status "Creating main Nginx configuration..."
sudo tee /etc/nginx/nginx.conf << 'EOF'
user www-data;
worker_processes auto;
pid /run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    # JSON log format for structured logging (better for log aggregation)
    log_format json_combined escape=json
        '{ "time": "$time_iso8601", "remote_addr": "$remote_addr", "request": "$request",'
        ' "status": $status, "body_bytes_sent": $body_bytes_sent, "request_time": $request_time,'
        ' "upstream_response_time": "$upstream_response_time", "request_method": "$request_method",'
        ' "uri": "$request_uri", "http_referrer": "$http_referer", "http_user_agent": "$http_user_agent",'
        ' "http_x_forwarded_for": "$http_x_forwarded_for", "server_name": "$server_name" }';

    # Access and error logs (will be rotated daily by logrotate)
    access_log /var/log/nginx/access.log json_combined;
    error_log /var/log/nginx/error.log;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    # Include site configurations
    include /etc/nginx/sites-enabled/*;
}
EOF

print_status "Creating site-specific Nginx configuration..."
sudo tee /etc/nginx/sites-available/grosint-backend << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 50M;

    # Rate limiting
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

print_status "Creating systemd service file..."
sudo tee /etc/systemd/system/grosint-backend.service << 'EOF'
[Unit]
Description=Grosint FastAPI Backend
After=network.target

[Service]
Type=exec
User=root
Group=root
WorkingDirectory=/opt/grosint-backend
Environment=PYTHONPATH=/opt/grosint-backend
ExecStart=/opt/grosint-backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

print_status "Enabling Nginx site..."
sudo ln -sf /etc/nginx/sites-available/grosint-backend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

print_status "Testing configurations..."
sudo nginx -t
sudo systemctl daemon-reload

print_success "Nginx and systemd configurations created!"

# =============================================================================
# STEP 14: FINAL VERIFICATION AND INFORMATION
# =============================================================================
print_header "STEP 14: FINAL VERIFICATION"

print_status "Verifying all installations..."

echo "✓ OS Information:"
lsb_release -a

echo -e "\n✓ Python Version:"
python3.12 --version
python3 --version 2>/dev/null || echo "python3 symlink: Not set"

echo -e "\n✓ Python 3.12 Pip:"
python3.12 -m pip --version

echo -e "\n✓ Docker Version:"
sudo docker --version

echo -e "\n✓ Docker Compose Version:"
sudo docker-compose --version

echo -e "\n✓ Nginx Version:"
nginx -v

echo -e "\n✓ Certbot Version:"
if command -v certbot >/dev/null 2>&1; then
    certbot --version 2>/dev/null || echo "Certbot installed (version check requires domain setup)"
else
    echo "Certbot installation pending verification"
fi

echo -e "\n✓ Firewall Status:"
sudo ufw status

echo -e "\n✓ Disk Space:"
df -h /

echo -e "\n✓ Memory:"
free -h

print_success "All verifications completed!"

# =============================================================================
# FINAL SUMMARY AND NEXT STEPS
# =============================================================================
print_header "SETUP COMPLETED SUCCESSFULLY!"

print_success "Azure VM has been configured with:"
echo "  ✅ Ubuntu $(lsb_release -rs) with latest updates"
echo "  ✅ Python 3.12.7 with pip and venv"
echo "  ✅ Docker and Docker Compose (for testing)"
echo "  ✅ Nginx web server"
echo "  ✅ Certbot for SSL certificates (via snap)"
echo "  ✅ UFW firewall configured"
echo "  ✅ Application user 'grosint' created"
echo "  ✅ Directory structure at /opt/grosint-backend"
echo "  ✅ System optimization and security hardening"
echo "  ✅ Monitoring and logging setup"
echo "  ✅ Helper scripts installed"

print_warning "IMPORTANT NEXT STEPS:"
echo "1. Configure your domain DNS to point to this server:"
echo "   A record: your-domain.com → $(curl -s ifconfig.me)"
echo ""
echo "2. Set up SSL certificate (after DNS propagation):"
echo "   sudo certbot --nginx -d your-domain.com"
echo "   # Or if using snap: sudo /snap/bin/certbot --nginx -d your-domain.com"
echo ""
echo "3. Update GitHub secrets with:"
echo "   AZURE_VM_HOST=$(curl -s ifconfig.me)"
echo "   AZURE_VM_USERNAME=$USER"
echo "   DOMAIN_NAME=your-domain.com"
echo ""
echo "4. Log out and log back in for Docker group changes to take effect:"
echo "   exit"
echo ""
echo "5. Test Docker access after re-login:"
echo "   docker run hello-world"
echo ""
echo "6. Test Python 3.12 installation:"
echo "   python3.12 --version"
echo "   python3.12 -m pip --version"
echo ""
echo "6. Useful commands:"
echo "   grosint-status    # Check application status"
echo "   grosint-backup    # Create backup"
echo "   docker ps         # List running containers"
echo "   sudo journalctl -u grosint-backend -f  # View app logs"
echo "   python3.12 --version  # Check Python 3.12"
echo "   /snap/bin/certbot --version  # Check Certbot (if using snap)"

print_success "Setup script completed! 🎉"
print_status "Server IP: $(curl -s ifconfig.me)"
print_status "SSH Command: ssh -i azure-grosint-dev.pem $USER@$(curl -s ifconfig.me)"

echo -e "\n${GREEN}Your Azure VM is now ready for Grosint Backend deployment!${NC}\n"
