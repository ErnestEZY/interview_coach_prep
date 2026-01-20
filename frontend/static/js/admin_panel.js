function panel(){
  return {
    q:'', status:'', tag:'', items:[], detail:null, tagsInput:'',
    userName: 'Guest', userEmail: '',
    page: 1, perPage: 5,
    sessionTime: 0,
    timerId: null,
    formatTime(seconds) {
      if (isNaN(seconds) || seconds === null || seconds === undefined) return '0:00';
      const totalSeconds = Math.max(0, Math.floor(seconds));
      const m = Math.floor(totalSeconds / 60);
      const s = totalSeconds % 60;
      return `${m}:${s.toString().padStart(2, '0')}`;
    },
    startTimer() {
      if (this.timerId) return;
      const token = icp.state.token;
      if (!token) return;
      const payload = icp.decodeToken(token);
      if (!payload || !payload.exp) return;
      const exp = payload.exp;
      localStorage.setItem('session_expiry_admin', exp);
      const now = Math.floor(Date.now() / 1000);
      this.sessionTime = Math.max(0, exp - now);
      this.timerId = setInterval(() => {
        if (this.sessionTime > 0) {
          this.sessionTime--;
        } else {
          clearInterval(this.timerId);
          this.timerId = null;
          localStorage.removeItem('session_expiry_admin');
          alert('Admin session has expired. Please login again.');
          icp.logout();
        }
      }, 1000);
    },
    get totalPages(){ return Math.ceil(this.items.length / this.perPage) || 1 },
    get paginatedItems(){
      const start = (this.page - 1) * this.perPage;
      return this.items.slice(start, start + this.perPage);
    },
    nextPage(){ if(this.page < this.totalPages) { this.page++; this.renderList(); } },
    prevPage(){ if(this.page > 1) { this.page--; this.renderList(); } },
    goToPage(p){
      const n = parseInt(p);
      if(n > 0 && n <= this.totalPages) { this.page = n; this.renderList(); }
      else { this.renderList(); } // Reset input
    },
    escapeHtml(s){ return String(s).replace(/[&<>"']/g, m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m])) },
    renderList(){
      const tbody = document.getElementById('list-body');
      if(!tbody) return;
      const rows = (this.paginatedItems||[]).map(it=>{
        const name = this.escapeHtml(it.filename || it.name || '(missing)');
        const status = this.escapeHtml(it.status || 'pending');
        const created = it.created_at ? new Date(it.created_at).toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' }) : '';
        const tags = Array.isArray(it.tags) && it.tags.length
          ? it.tags.map(t=>`<span class="badge bg-primary me-1">${this.escapeHtml(t)}</span>`).join('')
          : '<span class="text-secondary">—</span>';
        const statusClass = (it.status||'pending')==='approved' ? 'bg-success' : (it.status==='rejected' ? 'bg-danger' : 'bg-warning');
        const nameHtml = it.file_available ? `<a href="/static/pages/admin_file_preview.html?id=${this.escapeHtml(it.id)}" class="text-warning">${name}</a>` : name;
        const noteVal = this.escapeHtml(it.notes || '');
        const canNotify = it.status === 'approved' || it.status === 'rejected';
        const notifyBtn = `<button class="btn btn-outline-info btn-sm notify-btn w-100" data-id="${this.escapeHtml(it.id)}" ${canNotify ? '' : 'disabled'}>Notify</button>`;
        return `
          <tr>
            <td>${nameHtml}</td>
            <td><span class="badge ${statusClass}">${status}</span></td>
            <td>
              <div class="admin-tags-container">
                ${tags}
              </div>
            </td>
            <td>${created}</td>
            <td class="admin-notes-cell">
              <textarea rows="5" class="form-control admin-notes-textarea" placeholder="No notes" readonly>${noteVal}</textarea>
            </td>
            <td class="admin-actions-column">
              <div class="d-flex flex-column gap-2">
                <button class="btn btn-outline-light btn-sm detail-btn w-100" data-id="${this.escapeHtml(it.id)}">Details</button>
                ${notifyBtn}
              </div>
            </td>
          </tr>`;
      }).join('');
      tbody.innerHTML = rows;
      tbody.querySelectorAll('.detail-btn').forEach(btn=>{
        btn.addEventListener('click', ()=> this.open(btn.getAttribute('data-id')));
      });
      tbody.querySelectorAll('.notify-btn').forEach(btn=>{
        btn.addEventListener('click', ()=> this.notify(btn.getAttribute('data-id')));
      });
    },
    async init(){
      if(!icp.state.token){ window.location='/static/pages/admin.html'; return; }
      this.startTimer();
      try{
        const me = await fetch('/api/auth/me',{headers:{'Authorization':'Bearer '+icp.state.token}}).then(r=>r.json());
        if(!(me.role==='admin'||me.role==='super_admin')){ window.location='/static/pages/admin.html'; return; }
        // Use role instead of name as requested
        this.userName = (me.role || 'Admin').replace('_', ' ').toUpperCase();
        this.userEmail = me.email || '';
      }catch(e){
        window.location='/static/pages/admin.html'; return;
      }
      this.load();
    },
    load(){
      const u = new URL('/api/admin/resumes', window.location.origin);
      if(this.q) u.searchParams.set('q', this.q);
      if(this.status) u.searchParams.set('status', this.status);
      if(this.tag) u.searchParams.set('tag', this.tag);
      fetch(u, {headers:{'Authorization':'Bearer '+icp.state.token}})
        .then(r=>{
          if(r.status===401){ window.location.href='/static/pages/login.html'; return []; }
          if(r.status===403){ Swal.fire({icon:'error', title:'Forbidden', text:'Admin privileges required'}); return []; }
          return r.json();
        })
        .then(j=>{
          const arr = Array.isArray(j) ? j : [];
          this.items = arr.map(it=>({
            id: it.id,
            filename: it.filename || it.name || '',
            status: it.status || 'pending',
            tags: Array.isArray(it.tags) ? it.tags : [],
            created_at: it.created_at || null,
            file_available: !!it.file_available,
            notes: it.notes || ''
          }));
          this.page = 1;
          this.renderList();
        });
    },
    open(id){
      fetch('/api/admin/resumes/'+id, {headers:{'Authorization':'Bearer '+icp.state.token}})
        .then(r=>{
          if(r.status===401){ window.location.href='/static/pages/login.html'; return null; }
          if(r.status===403){ Swal.fire({icon:'error', title:'Forbidden', text:'Admin privileges required'}); return null; }
          return r.json();
        })
        .then(j=>{
          if(!j) return;
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
          this.tagsInput = (this.detail.tags||[]).join(',');
        });
    },
    save(){
      const tags = this.tagsInput.split(',').map(s=>s.trim()).filter(Boolean);
      const params = new URLSearchParams();
      params.set('status', this.detail.status || 'pending');
      params.set('notes', this.detail.notes || '');
      params.set('tags', JSON.stringify(tags));
      const btns = document.querySelectorAll('.admin-status-select, .quick-save-btn');
      btns.forEach(b=>b.disabled=true);
      fetch('/api/admin/resumes/'+this.detail.id, {
          method:'PATCH',
          headers:{'Authorization':'Bearer '+icp.state.token, 'Content-Type':'application/x-www-form-urlencoded'},
          body: params.toString()
        })
        .then(async r=>{
          if(r.status===401){ window.location.href='/static/pages/login.html'; return; }
          if(!r.ok){
            let msg = 'Save failed';
            try{ const j = await r.json(); msg = j.detail || msg; }catch(e){}
            Swal.fire({icon:'error', title:'Error', text: msg});
            return;
          }
          Swal.fire({icon:'success', title:'Saved', timer:1000, showConfirmButton:false});
          // Refresh detail to reflect updated fields
          return fetch('/api/admin/resumes/'+this.detail.id, {headers:{'Authorization':'Bearer '+icp.state.token}})
            .then(rr=>rr.json())
            .then(j=>{
              this.detail.status = j.status || this.detail.status;
              this.detail.notes = j.notes || this.detail.notes;
              this.detail.tags = Array.isArray(j.tags) ? j.tags : this.detail.tags;
              this.tagsInput = (this.detail.tags||[]).join(',');
              this.load();
            });
        })
        .finally(()=>{ btns.forEach(b=>b.disabled=false); });
    },
    async notify(id) {
      try {
        const res = await fetch('/api/admin/resumes/' + id, {
          headers: { 'Authorization': 'Bearer ' + icp.state.token }
        });
        if (!res.ok) throw new Error('Failed to fetch resume details');
        const data = await res.json();
        
        if (!data.user_email || data.user_email === 'unknown') {
          console.error('DEBUG: User email missing or unknown. user_id:', data.user_id);
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
    }
  }
}
