# update localization
ROOT_PATH=.
for po_file in $(find $ROOT_PATH/locale -name '*.po') ; do
    mo_file=${po_file%.po}.mo  
    python3 $ROOT_PATH/venv/Tools/i18n/msgfmt.py -o $mo_file $po_file ;
done
