# ... (Inside tabs[2]: --- CHAMPIONSHIP LOG ---)
        e_col, d_col = st.columns(2)
        with e_col:
            with st.expander("📝 Edit Result"):
                idx = st.number_input("Index to Edit", 0, len(df)-1, 0, key="c_edit_idx")
                t_to_edit = data[idx]
                with st.form("c_edit_form"):
                    new_pts = st.number_input("Points", 0.0, 100.0, float(t_to_edit.get('points', 0)))
                    new_cat = st.text_input("Category", t_to_edit.get('category'))
                    if st.form_submit_button("Save Changes"):
                        t_to_edit['points'] = new_pts
                        t_to_edit['category'] = new_cat
                        r.lset("champ_results_final", int(idx), json.dumps(t_to_edit))
                        
                        # Logic Match: Auto-sync cache on edit
                        rebuild_leaderboard_cache(r)
                        
                        st.success("Updated and Cache Rebuilt!")
                        st.rerun()
        with d_col:
            with st.expander("🗑️ Delete Result"):
                del_idx = st.number_input("Index to Delete", 0, len(df)-1, 0, key="c_del_idx")
                if st.button("Confirm Deletion"):
                    r.lset("champ_results_final", int(del_idx), "WIPE")
                    r.lrem("champ_results_final", 1, "WIPE")
                    
                    # Logic Match: Auto-sync cache on delete
                    rebuild_leaderboard_cache(r)
                    
                    st.success("Deleted and Cache Rebuilt!")
                    st.rerun()
