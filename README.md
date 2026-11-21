# Taif Architecture Mirror – Backend
cp .env.example .env  (fill OPENAI_API_KEY)
npm install && npm start

GET  /api/health | /api/style | /api/elements | /api/elements/:id | /api/documents
POST /api/chat            {messages:[{role,content}], stream?:true}  -> {reply} or SSE
POST /api/analyze-image   multipart image=<file>, lang=ar|en        -> JSON report + matchScore
POST /api/generate-image  {brief, buildingType?}                    -> {prompt, b64|url}
Drop text extracted from the official PDFs in data/extra/*.txt to ground the assistant further.

## Website
The site is served by the backend itself: open http://localhost:3000 after `npm start`.
public/index.html is the original demo bundle patched by tools/build_site.py
(real photo upload -> /api/analyze-image, real chat -> /api/chat, suggested render -> /api/generate-image).
Rebuild: python3 tools/build_site.py <original.html> public/index.html
