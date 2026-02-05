const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            q: '',
            status: '',
            tag: '',
            items: [],
            detail: null,
            tagsInput: '',
            userName: 'Guest',
            userEmail: '',
            page: 1,
            perPage: 5,
            sessionTime: 0,
            timerId: null,
            loading: false,
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
        }
    },
    mounted() {
        this.init();
        window.addEventListener('auth:changed', () => {
             if (!window.icp.state.token) {
                 window.location.href = '/static/pages/admin.html';
             }
        });
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
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                if (this.sessionTime <= 0) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                    localStorage.removeItem('session_expiry_admin');
                    alert('Admin session has expired. Please login again.');
                    window.icp.logout();
                }
            };
            
            updateTimer();
            this.timerId = setInterval(updateTimer, 1000);
        },
        async init() {
            if (!window.icp.state.token) {
                window.location.href = '/static/pages/admin.html';
                return;
            }
            this.startTimer();
            
            try {
                const me = await axios.get(window.icp.apiUrl('/api/auth/me')).then(r => r.data);
                if (!(me.role === 'admin' || me.role === 'super_admin')) {
                    window.location.href = '/static/pages/admin.html';
                    return;
                }
                this.userName = (me.role || 'Admin').replace('_', ' ').toUpperCase();
                this.userEmail = me.email || '';
            } catch (e) {
                console.error(e);
                window.location.href = '/static/pages/admin.html';
                return;
            }
            
            this.load();
        },
        async load() {
            this.detail = null; 
            this.loading = true;
            
            try {
                const params = {};
                if (this.q) params.q = this.q;
                if (this.status) params.status = this.status;
                if (this.tag) params.tag = this.tag;
                
                const response = await axios.get(window.icp.apiUrl('/api/admin/resumes'), { params });
                const data = response.data;
                
                if (!Array.isArray(data)) {
                    Swal.fire({ icon: 'error', title: 'Invalid Data', text: 'Expected array from server' });
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
                Swal.fire({ icon: 'error', title: 'Load Error', text: err.response?.data?.detail || err.message });
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
        async open(id) {
            try {
                const response = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${id}`));
                const j = response.data;
                if (!j) return;
                
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
            } catch (err) {
                console.error(err);
                Swal.fire({ icon: 'error', title: 'Error', text: 'Failed to load details' });
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
                
                Swal.fire({ icon: 'success', title: 'Saved', timer: 1000, showConfirmButton: false });
                
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
                Swal.fire({ icon: 'error', title: 'Error', text: err.response?.data?.detail || 'Save failed' });
            }
        },
        async notify(id) {
            try {
                const res = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${id}`));
                const data = res.data;
                
                if (!data.user_email || data.user_email === 'unknown') {
                    Swal.fire({ 
                        icon: 'error', 
                        title: 'Error', 
                        html: `User email not found for this resume.<br><div class="mt-2 small text-secondary">User ID: ${data.user_id || 'N/A'}</div>` 
                    });
                    return;
                }

                let message = '';
                if (data.status === 'approved') {
                    message = 'Your resume has been reviewed and meets the expected quality level. You may proceed with your job seeking. Good luck!';
                } else if (data.status === 'rejected') {
                    message = 'Your resume currently does not meet the expected quality level. Please revise your resume based on the feedback provided and readjust your content. Thank you.';
                } else {
                    Swal.fire({ icon: 'warning', title: 'Invalid Status', text: 'Notifications can only be sent for approved or rejected resumes.' });
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
                    Swal.fire({ icon: 'success', title: 'Notification Sent', text: 'The candidate has been notified via email.' });
                } else {
                    Swal.fire({ icon: 'error', title: 'Sending Failed', text: result.error });
                }
            } catch (err) {
                console.error(err);
                Swal.fire({ icon: 'error', title: 'Error', text: err.message });
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
                cancelButtonColor: '#3085d6',
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
                
                await Swal.fire('Deleted!', successMsg, 'success');
                this.detail = null;
                this.load();
            } catch (err) {
                console.error(err);
                Swal.fire('Error', err.response?.data?.detail || err.message, 'error');
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
