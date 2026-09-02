import streamlit as st
import pandas as pd
import io
import processor



st.title('Converter Rekening Koran')
uploaded_file = st.file_uploader('Upload rekening koran', type=['csv','pdf'])
bank_origin = st.selectbox('Pilih Bank',options=list(processor.PROCESSORS.keys()))


if st.button('Run'):
    if uploaded_file is None:
        st.error('😱 Belum ada file yang terpilih')
    else:
        status_placeholder = st.empty()
        status_placeholder.info('Processing...')
        
        file_type = uploaded_file.type
        filename = uploaded_file.name
        excel_filename = filename.rsplit(".", 1)[0] + '.xlsx'
        # st.write(file_type)
        
        try:
            data = processor.process(bank_origin,file_type,uploaded_file)
            df = pd.DataFrame(data)
            st.dataframe(df)
        except ValueError as e:
            st.error(str(e))
            status_placeholder.empty()
            st.stop()
        
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine="openpyxl")
        st.download_button(
            "📊 Download Excel",
            data=excel_buffer.getvalue(),
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        status_placeholder.empty()
        st.success('✅ Success!')