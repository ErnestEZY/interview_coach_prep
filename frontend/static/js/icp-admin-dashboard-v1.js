const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            q: '',
            status: '',
            tag: '',
            sortBy: 'newest',
            items: [],
            detail: null,
            // Object URL for the stored file shown in the detail panel, plus the
            // state of its fetch so the panel can say what is going on.
            detailPreviewUrl: '',
            detailFileState: 'idle',
            // Same rule as the viewer: the text is folded away while the
            // document is on screen, and the admin's own choice wins once made.
            detailExtractedOpen: false,
            _detailExtractedTouched: false,
            tagsInput: '',
            userName: 'Guest',
            userEmail: '',
            page: 1,
            perPage: 5,
            sessionTime: 0,
            timerId: null,
            loading: false,
            _isUnmounted: false,
            _popstateHandler: null,
            // Filter options
            statusOptions: [
                { value: '', label: 'Any status' },
                { value: 'pending', label: 'Pending' },
                { value: 'approved', label: 'Approved' },
                { value: 'rejected', label: 'Rejected' }
            ]
        };
    },
    computed: {
        logged() {
            return !!(window.icp && window.icp.state && window.icp.state.token);
        },
        totalPages() {
            return Math.ceil(this.items.length / this.perPage) || 1;
        },
        paginatedItems() {
            const start = (this.page - 1) * this.perPage;
            return this.items.slice(start, start + this.perPage);
        },
        displayItemsRangeStart() {
            return Math.min((this.page - 1) * this.perPage + 1, this.items.length);
        },
        displayItemsRangeEnd() {
            return Math.min(this.page * this.perPage, this.items.length);
        },
        // The extension is checked as well as the mime type: older records were
        // stored without one, and a PDF shown as text is the failure that
        // matters here.
        detailIsPdf() {
            const d = this.detail;
            if (!d) return false;
            return d.mime_type === 'application/pdf' || /\.pdf$/i.test(d.filename || '');
        },
        detailIsImage() {
            return !!(this.detail && /^image\//.test(this.detail.mime_type || ''));
        },
        // True when the document itself is in the panel, which is what makes
        // the extracted text optional rather than the only thing to read.
        detailRenderable() {
            return !!this.detailPreviewUrl && (this.detailIsPdf || this.detailIsImage);
        },
        detailFileNote() {
            if (this.detailFileState === 'loading') return 'Loading the file...';
            if (this.detailFileState === 'missing') return 'No file was stored for this submission.';
            if (this.detailFileState === 'ready' && !this.detailRenderable) {
                return 'This file type cannot be shown inline. Use "Open in new tab" above to read the original.';
            }
            return '';
        },
        extractedBlocks() {
            return window.icpResumeText
                ? window.icpResumeText.blocks(this.detail && this.detail.text)
                : [];
        }
    },
    mounted() {
        this.init();
        
        // Prevent back button to unauthenticated pages
        this._allowedAdminRoutes = [
            '/static/pages/icp-admin-view-2b8f4a10.html',
            '/static/pages/icp-admin-portal-5e6a1c3d.html'
        ];
        // Check current URL on load
        const checkCurrentUrl = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedAdminRoutes.some(route => currentPath.includes(route));
            if (!isAllowed && this.logged) {
                window.location.replace('/static/pages/icp-admin-portal-5e6a1c3d.html');
            }
        };
        checkCurrentUrl();
        // Popstate handler
        this._popstateHandler = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedAdminRoutes.some(route => currentPath.includes(route));
            if (!isAllowed) {
                // Push multiple entries to prevent back button
                history.replaceState(null, '', location.href);
                for (let i = 0; i < 5; i++) {
                    history.pushState(null, '', location.href);
                }
            } else {
                history.pushState(null, '', location.href);
            }
        };
        // Initialize history
        history.replaceState(null, '', location.href);
        for (let i = 0; i < 5; i++) {
            history.pushState(null, '', location.href);
        }
        window.addEventListener('popstate', this._popstateHandler);
        
        // Named listener for auth changes
        this._authListener = () => {
             if (!window.icp.state.token) {
                 window.location.href = "/static/pages/icp-admin-auth-9f2d8b4e.html";
             } else {
                 this.startTimer();
             }
        };
        window.addEventListener('auth:changed', this._authListener);
    },
    beforeUnmount() {
        this._isUnmounted = true;
        if (this.timerId) clearInterval(this.timerId);
        if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
        if (this._popstateHandler) window.removeEventListener('popstate', this._popstateHandler);
        this.releaseDetailFile();
    },
    methods: {
        formatTime(seconds) {
            if (isNaN(seconds) || seconds === null || seconds === undefined) return '0:00';
            const totalSeconds = Math.max(0, Math.floor(seconds));
            const m = Math.floor(totalSeconds / 60);
            const s = totalSeconds % 60;
            return `${m}:${s.toString().padStart(2, '0')}`;
        },
        formatDate(dateStr) {
            if (!dateStr) return '';
            if (window.dayjs) {
                return dayjs(dateStr).format('M/D/YYYY, h:mm:ss A');
            }
            return new Date(dateStr).toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' });
        },
        startTimer() {
            if (this.timerId) return;
            const token = window.icp.state.token;
            if (!token) return;
            
            const payload = window.icp.decodeToken(token);
            if (!payload || !payload.exp) return;
            
            const exp = payload.exp;
            localStorage.setItem('session_expiry_admin', exp);
            
            const updateTimer = () => {
                if (this._isUnmounted) {
                    if (this.timerId) {
                        clearInterval(this.timerId);
                        this.timerId = null;
                    }
                    return;
                }
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                if (this.sessionTime <= 0 && !this._isUnmounted) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                    localStorage.removeItem('session_expiry_admin');
                    Swal.fire({
                        icon: 'warning',
                        title: 'Session Expired',
                        text: 'Admin session has expired. Please login again to continue.',
                        confirmButtonText: 'Login Again',
                        confirmButtonColor: '#8b5cf6',
                        allowOutsideClick: false
                    }).then(() => {
                        window.icp.logout();
                    });
                }
            };
            
            updateTimer();
            this.timerId = setInterval(updateTimer, 1000);
        },
        async init() {
            if (!window.icp.state.token) {
                // Encoded login path: /static/pages/icp-admin-auth-9f2d8b4e.html
                window.location.href = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
                return;
            }
            this.startTimer();
            try {
                const me = await axios.get(window.icp.apiUrl('/api/auth/me')).then(r => r.data);
                this.userName = me.name || 'Admin';
                this.userEmail = me.email;
                if (!(me.role === 'admin' || me.role === 'super_admin')) {
                    // Encoded login path: /static/pages/icp-admin-auth-9f2d8b4e.html
                    window.location.href = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
                    return;
                }
            } catch (e) {
                // Encoded login path: /static/pages/icp-admin-auth-9f2d8b4e.html
                window.location.href = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
                return;
            }
            this.load();
        },
        viewResume(id) {
            // Encoded preview path: /static/pages/icp-admin-view-2b8f4a10.html
            const p = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tdmlldy0yYjhmNGExMC5odG1s');
            window.location.href = `${p}?id=${id}`;
        },
        async load() {
            this.releaseDetailFile();
            this.detail = null; 
            this.loading = true;
            
            try {
                const params = {};
                if (this.q) params.q = this.q;
                if (this.status) params.status = this.status;
                if (this.tag) params.tag = this.tag;
                params.sort = this.sortBy === 'oldest' ? 'oldest' : 'newest';
                
                const response = await axios.get(window.icp.apiUrl('/api/admin/resumes'), { params });
                
                if (this._isUnmounted) return;
                
                const data = response.data;
                
                if (!Array.isArray(data)) {
                    Swal.fire({ 
                        icon: 'error', 
                        title: 'Invalid Data', 
                        text: 'Expected array from server',
                        confirmButtonColor: '#8b5cf6'
                    });
                    this.items = [];
                } else {
                    this.items = data.map(it => ({
                        id: it.id || it._id || '',
                        filename: it.filename || it.name || '(no name)',
                        status: it.status || 'pending',
                        tags: Array.isArray(it.tags) ? it.tags : [],
                        created_at: it.created_at || null,
                        file_available: !!it.file_available,
                        notes: it.notes || ''
                    }));
                }
                this.page = 1;
            } catch (err) {
                console.error('Load error:', err);
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Load Error', 
                    text: err.response?.data?.detail || err.message,
                    confirmButtonColor: '#8b5cf6'
                });
            } finally {
                this.loading = false;
            }
        },
        nextPage() {
            if (this.page < this.totalPages) {
                this.page++;
            }
        },
        prevPage() {
            if (this.page > 1) {
                this.page--;
            }
        },
        goToPage(p) {
            const n = parseInt(p);
            if (n > 0 && n <= this.totalPages) {
                this.page = n;
            }
        },
        // The detail panel shows the stored document, so the bytes are fetched
        // as a blob: the file endpoint needs the bearer token, which an <iframe>
        // cannot send. The blob is then rendered from an object URL.
        openDetailFile(detail) {
            this.releaseDetailFile();
            if (!detail || !detail.file_available) {
                this.detailFileState = 'missing';
                this.syncDetailExtracted();
                return;
            }
            this.detailFileState = 'loading';
            axios.get(window.icp.apiUrl(`/api/admin/resumes/${detail.id}/file`), { responseType: 'blob' })
                .then((response) => {
                    // The panel may have been closed or switched while in flight.
                    if (this._isUnmounted || !this.detail || this.detail.id !== detail.id) return;
                    this.detailPreviewUrl = URL.createObjectURL(response.data);
                    this.detailFileState = 'ready';
                    this.syncDetailExtracted();
                })
                .catch((err) => {
                    if (this._isUnmounted) return;
                    if (err.response && err.response.status === 404) {
                        this.detailFileState = 'missing';
                        return;
                    }
                    // Anything else still leaves the token-bearing route as a
                    // way to reach the file.
                    this.detailPreviewUrl = window.icp.apiUrl(
                        `/api/admin/resumes/${detail.id}/file_open?token=${encodeURIComponent(window.icp.state.token)}`
                    );
                    this.detailFileState = 'ready';
                    this.syncDetailExtracted();
                });
        },
        releaseDetailFile() {
            if (this.detailPreviewUrl && this.detailPreviewUrl.startsWith('blob:')) {
                URL.revokeObjectURL(this.detailPreviewUrl);
            }
            this.detailPreviewUrl = '';
            this.detailFileState = 'idle';
        },
        onDetailExtractedToggle(event) {
            this._detailExtractedTouched = true;
            this.detailExtractedOpen = event.target.open;
        },
        // Opens the text only when there is no document to look at, and only
        // while the admin has expressed no preference.
        syncDetailExtracted() {
            if (!this._detailExtractedTouched) this.detailExtractedOpen = !this.detailRenderable;
        },
        closeDetail() {
            this.releaseDetailFile();
            this.detail = null;
        },
        async open(id) {
            try {
                const response = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${id}`));
                const j = response.data;
                if (!j) return;
                
                // A different submission may replace this one, so the previous
                // object URL is released before the panel is rebuilt.
                this.releaseDetailFile();
                this._detailExtractedTouched = false;
                this.detailExtractedOpen = false;
                this.detail = {
                    id: j.id,
                    filename: j.filename || '',
                    status: j.status || 'pending',
                    text: j.text || '',
                    notes: j.notes || '',
                    tags: Array.isArray(j.tags) ? j.tags : [],
                    created_at: j.created_at || null,
                    file_available: !!j.file_available,
                    mime_type: j.mime_type || ''
                };
                this.tagsInput = (this.detail.tags || []).join(',');
                this.openDetailFile(this.detail);

                // Scroll to detail section after Vue renders it
                this.$nextTick(() => {
                    const el = document.getElementById('detail-section');
                    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                });
            } catch (err) {
                console.error(err);
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Error', 
                    text: 'Failed to load details',
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },
        async save() {
            if (!this.detail) return;
            
            const tags = this.tagsInput.split(',').map(s => s.trim()).filter(Boolean);
            const params = new URLSearchParams();
            params.append('status', this.detail.status || 'pending');
            params.append('notes', this.detail.notes || '');
            params.append('tags', JSON.stringify(tags));
            
            try {
                await axios.patch(window.icp.apiUrl(`/api/admin/resumes/${this.detail.id}`), params, {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
                });
                
                Swal.fire({ 
                    icon: 'success', 
                    title: 'Saved', 
                    timer: 1000, 
                    showConfirmButton: false 
                });
                
                // Refresh detail
                const rr = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${this.detail.id}`));
                const j = rr.data;
                
                this.detail.status = j.status || this.detail.status;
                this.detail.notes = j.notes || this.detail.notes;
                this.detail.tags = Array.isArray(j.tags) ? j.tags : this.detail.tags;
                this.tagsInput = (this.detail.tags || []).join(',');
                
                this.load(); 
            } catch (err) {
                console.error(err);
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Error', 
                    text: err.response?.data?.detail || 'Save failed',
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },
        async notify(id, currentStatus) {
            if (currentStatus === 'pending') {
                Swal.fire({
                    icon: 'info',
                    title: 'Action Required',
                    text: 'Please update the resume status to "Approved" or "Rejected" before notifying the candidate.',
                    confirmButtonColor: '#8b5cf6'
                });
                return;
            }
            try {
                const res = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${id}`));
                const data = res.data;
                
                if (!data.user_email || data.user_email === 'unknown') {
                    Swal.fire({ 
                        icon: 'error', 
                        title: 'Error', 
                        html: `User email not found for this resume.<br><div class="mt-2 small" style="color: #475569; font-weight: 500;">User ID: ${data.user_id || 'N/A'}</div>`,
                        confirmButtonColor: '#8b5cf6'
                    });
                    return;
                }

                let message = '';
                if (data.status === 'approved') {
                    message = 'Your resume has been reviewed and meets the expected quality level. You may proceed with your job seeking. Good luck!';
                } else if (data.status === 'rejected') {
                    message = 'Your resume currently does not meet the expected quality level. Please revise your resume based on the feedback provided and readjust your content. Thank you.';
                } else {
                    Swal.fire({ 
                        icon: 'warning', 
                        title: 'Invalid Status', 
                        text: 'Notifications can only be sent for approved or rejected resumes.',
                        confirmButtonColor: '#8b5cf6'
                    });
                    return;
                }

                Swal.fire({
                    title: 'Sending Notification...',
                    text: 'Please wait while we notify the candidate.',
                    allowOutsideClick: false,
                    didOpen: () => Swal.showLoading()
                });

                const result = await sendAdminNotificationEmail(data.user_email, message);
                
                if (result.success) {
                    Swal.fire({ 
                        icon: 'success', 
                        title: 'Notification Sent', 
                        text: 'The candidate has been notified via email.',
                        confirmButtonColor: '#8b5cf6'
                    });
                } else {
                    Swal.fire({ 
                        icon: 'error', 
                        title: 'Sending Failed', 
                        text: result.error,
                        confirmButtonColor: '#8b5cf6'
                    });
                }
            } catch (err) {
                console.error(err);
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Error', 
                    text: err.message,
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },
        async deleteResume(id) {
            if (!id) return;
            
            const result = await Swal.fire({
                title: 'Are you sure?',
                text: "This will permanently delete this resume and its associated file.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#8b5cf6',
                confirmButtonText: 'Yes, delete it!'
            });
            
            if (!result.isConfirmed) return;
            
            try {
                const res = await axios.delete(window.icp.apiUrl(`/api/admin/resumes/${id}`));
                const data = res.data;
                
                let successMsg = 'The resume has been deleted.';
                if (data.gridfs_deleted) {
                    successMsg += ' Associated GridFS file was also removed.';
                }
                
                await Swal.fire({
                    title: 'Deleted!',
                    text: successMsg,
                    icon: 'success',
                    confirmButtonColor: '#8b5cf6'
                });
                this.detail = null;
                this.load();
            } catch (err) {
                console.error(err);
                Swal.fire({
                    title: 'Error',
                    text: err.response?.data?.detail || err.message,
                    icon: 'error',
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },
        getStatusClass(status) {
            if (status === 'approved') return 'bg-success';
            if (status === 'rejected') return 'bg-danger';
            return 'bg-warning';
        },
        logout() {
            window.icp.logout();
        }
    }
});

app.mount('#app');
