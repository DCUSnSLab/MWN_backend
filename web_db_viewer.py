#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
웹 기반 데이터베이스 뷰어

브라우저에서 pgAdmin처럼 데이터베이스 내용을 확인할 수 있는 간단한 웹 인터페이스입니다.
"""

from flask import Flask, render_template_string, request, jsonify
from app import app
from database import db
from models import User, Market, DamageStatus, Weather
import json
from datetime import datetime

# 웹 뷰어 HTML 템플릿
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>날씨 데이터베이스 뷰어</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f7;
            color: #1d1d1f;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { 
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            background: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .tab:hover { background: #f0f0f0; }
        .tab.active { background: #007AFF; color: white; }
        .content {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            min-height: 500px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-number { font-size: 2em; font-weight: bold; }
        .stat-label { opacity: 0.9; margin-top: 5px; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        tr:hover { background: #f8f9fa; }
        .filters {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .filter-input {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            min-width: 150px;
        }
        .refresh-btn {
            background: #34C759;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
        }
        .refresh-btn:hover { background: #30A46C; }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .table-container {
            max-height: 600px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
        }
        .json-view {
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
            white-space: pre-wrap;
            max-height: 200px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌤️ 날씨 데이터베이스 뷰어</h1>
            <p>데이터베이스의 모든 테이블과 데이터를 확인할 수 있습니다.</p>
        </div>

        <div class="tabs">
            <button class="tab active" onclick="showTab('overview')">📊 개요</button>
            <button class="tab" onclick="showTab('users')">👥 사용자</button>
            <button class="tab" onclick="showTab('markets')">🏪 시장</button>
            <button class="tab" onclick="showTab('weather')">🌤️ 날씨</button>
            <button class="tab" onclick="showTab('damage')">⚠️ 피해상태</button>
        </div>

        <div class="content" id="content">
            <div class="loading">데이터를 불러오는 중...</div>
        </div>
    </div>

    <script>
        let currentTab = 'overview';
        
        async function fetchData(endpoint) {
            try {
                const response = await fetch(`/db-viewer/api/${endpoint}`);
                return await response.json();
            } catch (error) {
                console.error('데이터 로드 오류:', error);
                return null;
            }
        }

        function formatDateTime(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleDateString('ko-KR') + ' ' + date.toLocaleTimeString('ko-KR');
        }

        function formatNumber(num) {
            return num ? num.toLocaleString() : '-';
        }

        async function showTab(tabName) {
            // 탭 활성화
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            event.target.classList.add('active');
            currentTab = tabName;

            const content = document.getElementById('content');
            content.innerHTML = '<div class="loading">데이터를 불러오는 중...</div>';

            let html = '';
            
            switch(tabName) {
                case 'overview':
                    html = await generateOverview();
                    break;
                case 'users':
                    html = await generateUsersTable();
                    break;
                case 'markets':
                    html = await generateMarketsTable();
                    break;
                case 'weather':
                    html = await generateWeatherTable();
                    break;
                case 'damage':
                    html = await generateDamageTable();
                    break;
            }
            
            content.innerHTML = html;
        }

        async function generateOverview() {
            const stats = await fetchData('stats');
            if (!stats) return '<div>데이터를 불러올 수 없습니다.</div>';

            return `
                <h2>📊 데이터베이스 개요</h2>
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">${formatNumber(stats.users)}</div>
                        <div class="stat-label">👥 사용자</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${formatNumber(stats.markets)}</div>
                        <div class="stat-label">🏪 시장</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${formatNumber(stats.weather_total)}</div>
                        <div class="stat-label">🌤️ 총 날씨 데이터</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${formatNumber(stats.weather_current)}</div>
                        <div class="stat-label">📍 현재 날씨</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${formatNumber(stats.weather_forecast)}</div>
                        <div class="stat-label">🔮 예보 데이터</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${formatNumber(stats.damage_statuses)}</div>
                        <div class="stat-label">⚠️ 피해 상태</div>
                    </div>
                </div>
                
                <h3>📈 최신 업데이트</h3>
                <p><strong>최근 날씨 업데이트:</strong> ${formatDateTime(stats.latest_weather_update)}</p>
                <p><strong>활성 시장:</strong> ${stats.active_markets}개</p>
                <p><strong>좌표 있는 시장:</strong> ${stats.markets_with_coordinates}개</p>
                
                <button class="refresh-btn" onclick="showTab('overview')">🔄 새로고침</button>
            `;
        }

        async function generateUsersTable() {
            const users = await fetchData('users');
            if (!users) return '<div>사용자 데이터를 불러올 수 없습니다.</div>';

            let html = `
                <h2>👥 사용자 (${users.length}명)</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>이름</th>
                                <th>이메일</th>
                                <th>전화번호</th>
                                <th>위치</th>
                                <th>활성</th>
                                <th>가입일</th>
                                <th>알림설정</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            users.forEach(user => {
                const notifications = user.notification_preferences ? 
                    JSON.stringify(user.notification_preferences) : '-';
                html += `
                    <tr>
                        <td>${user.id}</td>
                        <td>${user.name}</td>
                        <td>${user.email}</td>
                        <td>${user.phone || '-'}</td>
                        <td>${user.location || '-'}</td>
                        <td>${user.is_active ? '🟢' : '🔴'}</td>
                        <td>${formatDateTime(user.created_at)}</td>
                        <td><div class="json-view">${notifications}</div></td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div>';
            return html;
        }

        async function generateMarketsTable() {
            const markets = await fetchData('markets');
            if (!markets) return '<div>시장 데이터를 불러올 수 없습니다.</div>';

            let html = `
                <h2>🏪 시장 (${markets.length}개)</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>이름</th>
                                <th>위치</th>
                                <th>위도</th>
                                <th>경도</th>
                                <th>카테고리</th>
                                <th>활성</th>
                                <th>등록일</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            markets.forEach(market => {
                html += `
                    <tr>
                        <td>${market.id}</td>
                        <td>${market.name}</td>
                        <td>${market.location}</td>
                        <td>${market.latitude || '-'}</td>
                        <td>${market.longitude || '-'}</td>
                        <td>${market.category || '-'}</td>
                        <td>${market.is_active ? '🟢' : '🔴'}</td>
                        <td>${formatDateTime(market.created_at)}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div>';
            return html;
        }

        async function generateWeatherTable() {
            const weather = await fetchData('weather');
            if (!weather) return '<div>날씨 데이터를 불러올 수 없습니다.</div>';

            let html = `
                <h2>🌤️ 날씨 데이터 (${weather.length}개)</h2>
                <div class="filters">
                    <select class="filter-input" onchange="filterWeather(this.value)">
                        <option value="">전체 타입</option>
                        <option value="current">현재 날씨</option>
                        <option value="forecast">예보</option>
                    </select>
                    <input type="text" class="filter-input" placeholder="지역 검색..." 
                           onkeyup="searchWeather(this.value)">
                    <button class="refresh-btn" onclick="showTab('weather')">🔄 새로고침</button>
                </div>
                <div class="table-container">
                    <table id="weather-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>지역</th>
                                <th>타입</th>
                                <th>기온</th>
                                <th>습도</th>
                                <th>강수량</th>
                                <th>풍속</th>
                                <th>풍향</th>
                                <th>하늘상태</th>
                                <th>수집시간</th>
                            </tr>
                        </thead>
                        <tbody id="weather-tbody">
            `;
            
            weather.forEach(w => {
                html += `
                    <tr>
                        <td>${w.id}</td>
                        <td>${w.location_name || '-'}</td>
                        <td>${w.api_type}</td>
                        <td>${w.temp ? w.temp + '°C' : '-'}</td>
                        <td>${w.humidity ? w.humidity + '%' : '-'}</td>
                        <td>${w.rain_1h ? w.rain_1h + 'mm' : '-'}</td>
                        <td>${w.wind_speed ? w.wind_speed + 'm/s' : '-'}</td>
                        <td>${w.wind_direction ? w.wind_direction + '°' : '-'}</td>
                        <td>${w.sky || '-'}</td>
                        <td>${formatDateTime(w.created_at)}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div>';
            return html;
        }

        async function generateDamageTable() {
            const damages = await fetchData('damage');
            if (!damages) return '<div>피해상태 데이터를 불러올 수 없습니다.</div>';

            let html = `
                <h2>⚠️ 피해상태 (${damages.length}건)</h2>
            `;
            
            if (damages.length === 0) {
                html += '<p>등록된 피해상태가 없습니다.</p>';
                return html;
            }
            
            html += `
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>시장ID</th>
                                <th>기상이벤트</th>
                                <th>피해수준</th>
                                <th>설명</th>
                                <th>신고일</th>
                                <th>해결여부</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            damages.forEach(damage => {
                html += `
                    <tr>
                        <td>${damage.id}</td>
                        <td>${damage.market_id}</td>
                        <td>${damage.weather_event}</td>
                        <td>${damage.damage_level}</td>
                        <td>${damage.description || '-'}</td>
                        <td>${formatDateTime(damage.reported_at)}</td>
                        <td>${damage.is_resolved ? '✅' : '❌'}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div>';
            return html;
        }

        // 초기 로드
        window.onload = () => showTab('overview');
    </script>
</body>
</html>
"""

@app.route('/db-viewer')
def db_viewer():
    """데이터베이스 뷰어 메인 페이지"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/db-viewer/api/stats')
def api_stats():
    """데이터베이스 통계 API"""
    with app.app_context():
        stats = {
            'users': User.query.count(),
            'markets': Market.query.count(),
            'weather_total': Weather.query.count(),
            'weather_current': Weather.query.filter_by(api_type='current').count(),
            'weather_forecast': Weather.query.filter_by(api_type='forecast').count(),
            'damage_statuses': DamageStatus.query.count(),
            'active_markets': Market.query.filter_by(is_active=True).count(),
            'markets_with_coordinates': Market.query.filter(
                Market.latitude.isnot(None), 
                Market.longitude.isnot(None)
            ).count(),
            'latest_weather_update': None
        }
        
        # 최근 날씨 업데이트 시간
        latest_weather = Weather.query.order_by(Weather.created_at.desc()).first()
        if latest_weather:
            stats['latest_weather_update'] = latest_weather.created_at.isoformat()
        
        return jsonify(stats)

@app.route('/db-viewer/api/users')
def api_users():
    """사용자 데이터 API"""
    with app.app_context():
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])

@app.route('/db-viewer/api/markets')
def api_markets():
    """시장 데이터 API"""
    with app.app_context():
        markets = Market.query.all()
        return jsonify([market.to_dict() for market in markets])

@app.route('/db-viewer/api/weather')
def api_weather():
    """날씨 데이터 API"""
    with app.app_context():
        limit = request.args.get('limit', 100, type=int)
        weather_data = Weather.query.order_by(Weather.created_at.desc()).limit(limit).all()
        return jsonify([weather.to_dict() for weather in weather_data])

@app.route('/db-viewer/api/damage')
def api_damage():
    """피해상태 데이터 API"""
    with app.app_context():
        damages = DamageStatus.query.all()
        return jsonify([damage.to_dict() for damage in damages])

if __name__ == '__main__':
    print("🌐 웹 데이터베이스 뷰어를 시작합니다...")
    print("브라우저에서 http://localhost:8000/db-viewer 를 열어주세요.")
    app.run(debug=True, host='0.0.0.0', port=8000)