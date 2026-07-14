# Stage 1: Build the React application
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency configs
COPY package.json package-lock.json* ./

# Install npm packages
RUN npm install

# Copy application files
COPY index.html vite.config.js ./
COPY public/ public/
COPY src/ src/

# Compile React/Vite assets
RUN npm run build

# Stage 2: Serve static files using Nginx
FROM nginx:alpine

# Copy built files from stage 1
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose web server port
EXPOSE 80

# Run Nginx
CMD ["nginx", "-g", "daemon off;"]
