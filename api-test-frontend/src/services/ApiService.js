const BASE_URL = 'https://staging-api.hiwajo.com/api';

class ApiService {
    constructor() {
        this.token = localStorage.getItem('wajo_token') || '';
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('wajo_token', token);
    }

    async request(endpoint, options = {}) {
        const url = `${BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers,
            });

            const data = await response.json();

            return {
                ok: response.ok,
                status: response.status,
                data,
            };
        } catch (error) {
            console.error('API Request failed:', error);
            return {
                ok: false,
                status: 0,
                data: { error: 'Network error or request failed', details: error.message },
            };
        }
    }

    // Auth
    sendOtp(phone_no) {
        return this.request('/auth/send-otp', {
            method: 'POST',
            body: JSON.stringify({ phone_no }),
        });
    }

    login(data) {
        // data: { phone_no, otp, selected_language, fcm_token }
        return this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // Shares
    getSharedByMe() {
        return this.request('/vision/clip-reels/shared-by-me/');
    }

    getSharedWithMe() {
        return this.request('/vision/clip-reels/shared-with-me/');
    }

    getSharedWithMeBySession(sessionId) {
        return this.request(`/vision/clip-reels/shared-with-me/${sessionId}/`);
    }

    // Clip Reels
    getAllClipReels() {
        return this.request('/vision/clip-reels/');
    }

    // Comments
    getComments(clipReelId) {
        return this.request(`/vision/clip-reels/${clipReelId}/comments/`);
    }

    addComment(clipReelId, content, visibility = 'public') {
        return this.request(`/vision/clip-reels/${clipReelId}/comments/`, {
            method: 'POST',
            body: JSON.stringify({ content, visibility }),
        });
    }

    // Notes
    getNotes(clipReelId) {
        return this.request(`/vision/clip-reels/${clipReelId}/notes/`);
    }

    addNote(clipReelId, data) {
        return this.request(`/vision/clip-reels/${clipReelId}/notes/`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    addBulkNotes(clipReelId, notes) {
        return this.request(`/vision/clip-reels/${clipReelId}/notes/bulk/`, {
            method: 'POST',
            body: JSON.stringify({ notes }),
        });
    }

    // Highlights
    getSessionHighlights(sessionId, params = {}) {
        const query = new URLSearchParams(params).toString();
        const endpoint = `/vision/highlights/${sessionId}/${query ? `?${query}` : ''}`;
        return this.request(endpoint);
    }

    getLegacySessionHighlights(sessionId) {
        return this.request(`/vision/sessions/${sessionId}/highlights/`);
    }

    shareClipBulk(data) {
        return this.request('/vision/highlights/share/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // Note Replies
    replyToNote(noteId, content) {
        return this.request(`/vision/notes/${noteId}/reply/`, {
            method: 'POST',
            body: JSON.stringify({ content }),
        });
    }

    getNoteReplies(noteId) {
        return this.request(`/vision/notes/${noteId}/replies/`);
    }

    // Users
    getUserProfile() {
        return this.request('/auth/user-profile');
    }

    getSessionUsers(sessionId) {
        return this.request(`/vision/get_user/${sessionId}/`);
    }
}

export default new ApiService();
