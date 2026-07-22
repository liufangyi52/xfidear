This package already includes:
1. Xfplus frontend, backend, data, scripts, and portable runtimes.
2. miniprogram source code.

Run the web platform directly:
1. Extract the whole zip file.
2. Double click Start-App.bat.
3. The browser opens http://127.0.0.1:8000/app

Edit and develop:
1. Double click Start-Dev.bat.
2. Frontend: http://127.0.0.1:5173/
3. Backend:  http://127.0.0.1:8000/api/health
4. Rebuild frontend after edits with Rebuild-Frontend.bat.
5. Stop dev mode with Stop-Dev.bat.

Included by default:
- Portable Python and Node.js.
- frontend/node_modules already included.
- backend dependencies already included.
- Safe .env without sender machine keys.
- AI defaults to mock mode.

Mini program note:
- Mini program source is in the miniprogram folder.
- Running the mini program still requires WeChat DevTools.
- That is a platform requirement, not a missing project environment.

Demo accounts:
- city_demo / 123456
- county_admin_demo / 123456
- community_admin_demo / 123456
- resident_demo / 123456
- tourist_demo / 123456